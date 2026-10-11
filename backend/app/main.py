from fastapi import FastAPI

from app.common.csrf import CSRFMiddleware
from app.common.errors import install_error_handlers
from app.config.settings import get_settings


def create_app() -> FastAPI:
    from app.config.settings import validate_secrets
    from app.llm.deps import validate_llm_config

    validate_secrets()
    validate_llm_config()
    app = FastAPI(
        title="ФСП: платформа обратного найма",
        version="0.1.0",
        openapi_url="/api/v1/openapi.json",
        docs_url="/api/v1/docs",
        redoc_url="/api/v1/redoc",
    )
    install_error_handlers(app)
    app.add_middleware(CSRFMiddleware)

    from app.auth.router import router as auth_router

    app.include_router(auth_router, prefix="/api/v1")

    from app.fsp.router import router as fsp_router

    app.include_router(fsp_router, prefix="/api/v1")

    from app.candidates.router import router as candidate_router

    app.include_router(candidate_router, prefix="/api/v1")

    from app.assessment.router import router as assessment_router

    app.include_router(assessment_router, prefix="/api/v1")

    from app.employers.router import router as employer_router

    app.include_router(employer_router, prefix="/api/v1")

    from app.matching.router import router as matching_router

    app.include_router(matching_router, prefix="/api/v1")

    from app.contacts.router import router as contacts_router

    app.include_router(contacts_router, prefix="/api/v1")

    from app.hiring.router import router as hiring_router

    app.include_router(hiring_router, prefix="/api/v1")

    from app.moderation.router import router as moderation_router

    app.include_router(moderation_router, prefix="/api/v1")

    from app.initiative.router import router as initiative_router

    app.include_router(initiative_router, prefix="/api/v1")

    from app.employer_tasks.router import router as employer_tasks_router

    app.include_router(employer_tasks_router, prefix="/api/v1")

    from app.integrations.router import router as integrations_router

    app.include_router(integrations_router, prefix="/api/v1")

    from app.groups.router import router as groups_router

    app.include_router(groups_router, prefix="/api/v1")

    from app.junior.router import router as junior_router

    app.include_router(junior_router, prefix="/api/v1")

    from app.trust.router import router as trust_router

    app.include_router(trust_router, prefix="/api/v1")

    from app.vacancies.router import router as vacancies_router

    app.include_router(vacancies_router, prefix="/api/v1")

    from app.notifications.router import router as notifications_router

    app.include_router(notifications_router, prefix="/api/v1")

    from app.lab.router import router as lab_router

    app.include_router(lab_router, prefix="/api/v1")

    if get_settings().mocks_on:
        # Роуты, а не app.mount: так на мок действуют те же зависимости и их подмены в тестах
        from app.mocks.fsp.router import router as fsp_mock_router

        app.include_router(fsp_mock_router, prefix="/mock/fsp", include_in_schema=False)

        from app.mocks.ats.router import router as ats_mock_router
        from app.mocks.dadata.router import router as dadata_mock_router

        app.include_router(ats_mock_router, prefix="/mock/ats", include_in_schema=False)

        app.include_router(dadata_mock_router, prefix="/mock/dadata", include_in_schema=False)

    from app.demo.router import router as demo_router

    app.include_router(demo_router, prefix="/api/v1", include_in_schema=get_settings().demo_mode)

    @app.get("/api/v1/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
