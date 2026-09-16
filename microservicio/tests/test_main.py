# origen: rag-banking-agent@c7e5f54
from app.main import create_app


async def test_create_app_lifespan():
    app = create_app()
    async with app.router.lifespan_context(app):
        assert app.state.engine is None
    assert app.state.engine is None
