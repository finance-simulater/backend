from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.v1.simulation.schema import SimulationStateResponse, TurnChoiceRequest, TurnResponse
from app.api.v1.simulation.service import SimulationService
from app.database import get_db

router = APIRouter(prefix="/api/v1/simulation", tags=["simulation"])


def get_simulation_service(db: Session = Depends(get_db)) -> SimulationService:
    return SimulationService(db)


@router.get("/users/{user_id}", response_model=SimulationStateResponse)
async def get_dashboard(user_id: int, service: SimulationService = Depends(get_simulation_service)):
    return service.get_state(user_id)


@router.get("/users/{user_id}/turns", response_model=list[TurnResponse])
async def list_turns(
    user_id: int,
    cursor: int | None = Query(None),
    size: int = Query(20, gt=0),
    service: SimulationService = Depends(get_simulation_service),
):
    return service.list_turns(user_id, cursor, size)


@router.post(
    "/users/{user_id}/turns",
    response_model=TurnResponse,
    status_code=status.HTTP_201_CREATED,
)
async def advance_turn(
    user_id: int,
    choice: TurnChoiceRequest,
    service: SimulationService = Depends(get_simulation_service),
):
    return service.advance_turn(user_id, choice)


@router.get("/users/{user_id}/turns/{turn_number}", response_model=TurnResponse)
async def get_turn(
    user_id: int,
    turn_number: int,
    service: SimulationService = Depends(get_simulation_service),
):
    return service.get_turn(user_id, turn_number)
