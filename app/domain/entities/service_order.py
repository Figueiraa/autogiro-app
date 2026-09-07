from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.domain.exceptions.domain_exceptions import InvalidStatusTransitionError
from app.domain.value_objects.service_order_status import VALID_TRANSITIONS, ServiceOrderStatus


@dataclass
class ServiceOrderItem:
    """Serviço aplicado a uma Ordem de Serviço."""

    service_type_id: int
    quantity: int
    unit_price: float
    id: int | None = None


@dataclass
class ServiceOrderPart:
    """Peça/insumo consumido em uma Ordem de Serviço."""

    part_id: int
    quantity: int
    unit_price: float
    id: int | None = None


@dataclass
class ServiceOrder:
    """Entidade de domínio da Ordem de Serviço (Python puro, sem ORM)."""

    number: str
    vehicle_id: int
    client_id: int
    total_budget: float
    status: ServiceOrderStatus = ServiceOrderStatus.RECEBIDA
    notes: str | None = None
    items: list[ServiceOrderItem] = field(default_factory=list)
    parts: list[ServiceOrderPart] = field(default_factory=list)
    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    delivered_at: datetime | None = None

    def transition_to(
        self, new_status: ServiceOrderStatus, now: datetime | None = None
    ) -> tuple[ServiceOrderStatus, float | None]:
        """Transiciona o status respeitando a máquina de estados do domínio.

        Registra o instante das transições relevantes (início, conclusão, entrega).
        Levanta ``InvalidStatusTransitionError`` se a transição não for permitida.

        Devolve o status que está sendo deixado e há quantos segundos a OS estava
        nele — o dado que alimenta a métrica de tempo médio por status. O tempo é
        ``None`` quando não há marco anterior conhecido (OS recém-carregada de um
        banco sem ``updated_at``).
        """
        if new_status not in VALID_TRANSITIONS[self.status]:
            raise InvalidStatusTransitionError(self.status.value, new_status.value)

        moment = now or datetime.now(UTC)
        anterior = self.status
        permanencia = _segundos_desde(self.updated_at or self.created_at, moment)

        if new_status == ServiceOrderStatus.EM_EXECUCAO:
            self.started_at = moment
        elif new_status == ServiceOrderStatus.FINALIZADA:
            self.completed_at = moment
        elif new_status == ServiceOrderStatus.ENTREGUE:
            self.delivered_at = moment

        self.status = new_status
        self.updated_at = moment
        return anterior, permanencia


def _segundos_desde(marco: datetime | None, agora: datetime) -> float | None:
    """Segundos entre dois instantes, tolerando timestamps sem fuso.

    O SQLite dos testes devolve datetimes *naive* e o PostgreSQL devolve
    *aware* (TIMESTAMPTZ). Subtrair um do outro levanta TypeError, então os
    naive são assumidos em UTC — que é como a aplicação sempre grava.
    """
    if marco is None:
        return None

    if marco.tzinfo is None:
        marco = marco.replace(tzinfo=UTC)
    if agora.tzinfo is None:
        agora = agora.replace(tzinfo=UTC)

    return max((agora - marco).total_seconds(), 0.0)
