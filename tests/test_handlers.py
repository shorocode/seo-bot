import pytest
from unittest.mock import AsyncMock, MagicMock
from telegram import Update, Message, Chat
from handlers.content_analysis import content_analyzer

@pytest.mark.asyncio
async def test_keyword_analysis_handler():
    # Setup
    update = Update(
        update_id=1,
        message=Message(
            message_id=1,
            chat=Chat(id=1, type='private'),
            text="Test text for analysis"
        )
    )
    context = MagicMock()
    
    # Mock external dependencies
    content_analyzer.analyze_keyword_density = AsyncMock(return_value={
        "keywords": ["test", "analysis"],
        "suggestions": "Some suggestions"
    })
    
    # Execute
    result = await content_analyzer.analyze_keyword_density(update, context, update.message.text)
    
    # Verify
    assert "keywords" in result
    assert "suggestions" in result
    assert isinstance(result["keywords"], list)
