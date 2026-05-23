from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from application.services import WorkerService
from presentation.api import router, set_worker_service

app = FastAPI(title="Concurrency Dashboard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

worker_service = WorkerService(num_workers=2)
set_worker_service(worker_service)


@app.on_event("startup")
def startup() -> None:
    worker_service.start()


app.include_router(router)
