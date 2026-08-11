from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.v1.auth.dependencies import get_current_user
from app.api.v1.simulation.schema import SimulationStateResponse, TurnChoiceRequest, TurnResponse
from app.api.v1.simulation.service import SimulationService
from app.api.v1.user.model import User
from app.database import get_db

router = APIRouter(prefix="/api/v1/simulation", tags=["simulation"])


def get_simulation_service(db: Session = Depends(get_db)) -> SimulationService:
    return SimulationService(db)


@router.get("", response_model=SimulationStateResponse)
async def get_dashboard(
    current_user: User = Depends(get_current_user),
    service: SimulationService = Depends(get_simulation_service),
):
    return service.get_state(current_user.id)


@router.get("/turns", response_model=list[TurnResponse])
async def list_turns(
    cursor: int | None = Query(None),
    size: int = Query(20, gt=0, le=100),
    current_user: User = Depends(get_current_user),
    service: SimulationService = Depends(get_simulation_service),
):
    return service.list_turns(current_user.id, cursor, size)


@router.post(
    "/turns",
    response_model=TurnResponse,
    status_code=status.HTTP_201_CREATED,
)
async def advance_turn(
    choice: TurnChoiceRequest,
    current_user: User = Depends(get_current_user),
    service: SimulationService = Depends(get_simulation_service),
):
    return service.advance_turn(current_user.id, choice)


@router.get("/turns/{turn_number}", response_model=TurnResponse)
async def get_turn(
    turn_number: int,
    current_user: User = Depends(get_current_user),
    service: SimulationService = Depends(get_simulation_service),
):
    return service.get_turn(current_user.id, turn_number)
