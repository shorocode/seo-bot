from typing import Optional, Dict
from enum import Enum
import stripe
from pydantic import BaseModel, validator
from config import settings
from utils.error_handling import PaymentError
import logging

logger = logging.getLogger(__name__)

class PaymentPlan(Enum):
    """انواع پلن‌های پرداخت"""
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"

class PaymentResult(BaseModel):
    """نتیجه پرداخت"""
    success: bool
    transaction_id: Optional[str]
    amount: float
    currency: str = "usd"
    user_id: int
    plan: PaymentPlan

class PaymentProcessor:
    """سیستم پرداخت امن با Stripe"""
    
    def __init__(self):
        stripe.api_key = settings.STRIPE_SECRET_KEY
        self.webhook_secret = settings.STRIPE_WEBHOOK_SECRET
        self.plans = {
            PaymentPlan.BASIC: 990,
            PaymentPlan.PRO: 2990,
            PaymentPlan.ENTERPRISE: 9990
        }

    async def create_subscription(
        self,
        user_id: int,
        plan: PaymentPlan,
        token: str,
        coupon: Optional[str] = None
    ) -> PaymentResult:
        """ایجاد اشتراک جدید"""
        try:
            customer = stripe.Customer.create(
                source=token,
                metadata={'user_id': str(user_id)}
            )
            
            subscription = stripe.Subscription.create(
                customer=customer.id,
                items=[{
                    'price': self._get_plan_id(plan),
                }],
                coupon=coupon,
                expand=['latest_invoice.payment_intent']
            )
            
            return PaymentResult(
                success=True,
                transaction_id=subscription.id,
                amount=self.plans[plan] / 100,
                user_id=user_id,
                plan=plan
            )
        except stripe.error.StripeError as e:
            logger.error(f"Payment failed: {str(e)}")
            raise PaymentError("Payment processing failed")

    def _get_plan_id(self, plan: PaymentPlan) -> str:
        """دریافت شناسه پلن از Stripe"""
        plan_ids = {
            PaymentPlan.BASIC: settings.STRIPE_BASIC_PLAN,
            PaymentPlan.PRO: settings.STRIPE_PRO_PLAN,
            PaymentPlan.ENTERPRISE: settings.STRIPE_ENTERPRISE_PLAN
        }
        return plan_ids[plan]

    async def handle_webhook(self, payload: bytes, sig_header: str) -> bool:
        """پردازش وب‌هوک Stripe"""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            
            if event['type'] == 'invoice.payment_succeeded':
                return await self._process_payment(event['data']['object'])
                
            return True
        except ValueError as e:
            raise PaymentError("Invalid payload")
        except stripe.error.SignatureVerificationError as e:
            raise PaymentError("Invalid signature")

# نمونه Singleton
payment_processor = PaymentProcessor()
