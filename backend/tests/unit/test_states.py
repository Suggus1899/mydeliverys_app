import pytest

from app.domain.errors import DomainError
from app.domain.states import TRANSITIONS, OrderStatus, transition


class TestOrderStatus:
    def test_all_statuses_defined(self):
        expected = {
            "PAYMENT_1_PENDING",
            "PAYMENT_1_VERIFYING",
            "PREPARING",
            "READY_FOR_PICKUP",
            "ON_THE_WAY",
            "ARRIVED_AT_CUSTOMER",
            "PAYMENT_2_VERIFYING",
            "DELIVERED",
            "CANCELLED",
            "REJECTED",
            "CANCELLED_WITH_REFUND",
            "DELIVERY_FAILED",
        }
        actual = {s.value for s in OrderStatus}
        assert actual == expected


class TestTransitions:
    def test_valid_transitions_from_payment_1_pending(self):
        allowed = TRANSITIONS[OrderStatus.PAYMENT_1_PENDING]
        assert OrderStatus.PAYMENT_1_VERIFYING in allowed
        assert OrderStatus.CANCELLED in allowed
        assert len(allowed) == 2

    def test_valid_transitions_from_payment_1_verifying(self):
        allowed = TRANSITIONS[OrderStatus.PAYMENT_1_VERIFYING]
        assert OrderStatus.PAYMENT_1_PENDING in allowed
        assert OrderStatus.PREPARING in allowed
        assert OrderStatus.CANCELLED in allowed
        assert OrderStatus.REJECTED in allowed
        assert len(allowed) == 4

    def test_valid_transitions_from_preparing(self):
        allowed = TRANSITIONS[OrderStatus.PREPARING]
        assert OrderStatus.READY_FOR_PICKUP in allowed
        assert OrderStatus.CANCELLED_WITH_REFUND in allowed
        assert len(allowed) == 2

    def test_valid_transitions_from_ready_for_pickup(self):
        allowed = TRANSITIONS[OrderStatus.READY_FOR_PICKUP]
        assert OrderStatus.ON_THE_WAY in allowed
        assert OrderStatus.CANCELLED_WITH_REFUND in allowed
        assert len(allowed) == 2

    def test_valid_transitions_from_on_the_way(self):
        allowed = TRANSITIONS[OrderStatus.ON_THE_WAY]
        assert OrderStatus.ARRIVED_AT_CUSTOMER in allowed
        assert OrderStatus.CANCELLED_WITH_REFUND in allowed
        assert len(allowed) == 2

    def test_valid_transitions_from_arrived_at_customer(self):
        allowed = TRANSITIONS[OrderStatus.ARRIVED_AT_CUSTOMER]
        assert OrderStatus.PAYMENT_2_VERIFYING in allowed
        assert OrderStatus.DELIVERED in allowed
        assert OrderStatus.DELIVERY_FAILED in allowed
        assert len(allowed) == 3

    def test_valid_transitions_from_payment_2_verifying(self):
        allowed = TRANSITIONS[OrderStatus.PAYMENT_2_VERIFYING]
        assert OrderStatus.ARRIVED_AT_CUSTOMER in allowed
        assert OrderStatus.DELIVERED in allowed
        assert len(allowed) == 2

    def test_terminal_states_have_no_transitions(self):
        for status in [
            OrderStatus.DELIVERED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
            OrderStatus.CANCELLED_WITH_REFUND,
            OrderStatus.DELIVERY_FAILED,
        ]:
            assert TRANSITIONS[status] == frozenset()

    def test_no_backwards_transitions(self):
        forward_flow = [
            OrderStatus.PAYMENT_1_PENDING,
            OrderStatus.PAYMENT_1_VERIFYING,
            OrderStatus.PREPARING,
            OrderStatus.READY_FOR_PICKUP,
            OrderStatus.ON_THE_WAY,
            OrderStatus.ARRIVED_AT_CUSTOMER,
            OrderStatus.PAYMENT_2_VERIFYING,
            OrderStatus.DELIVERED,
        ]

        for i, status in enumerate(forward_flow):
            allowed = TRANSITIONS[status]
            for target in allowed:
                if target in forward_flow:
                    target_idx = forward_flow.index(target)
                    if target_idx < i and not (
                        status == OrderStatus.PAYMENT_1_VERIFYING
                        and target == OrderStatus.PAYMENT_1_PENDING
                    ):
                        if not (
                            status == OrderStatus.PAYMENT_2_VERIFYING
                            and target == OrderStatus.ARRIVED_AT_CUSTOMER
                        ):
                            pytest.fail(
                                f"Backwards transition: {status} -> {target} "
                                f"(index {i} -> {target_idx})"
                            )


class TestTransitionFunction:
    def test_valid_transition(self):
        result = transition(OrderStatus.PAYMENT_1_PENDING, OrderStatus.PAYMENT_1_VERIFYING)
        assert result == OrderStatus.PAYMENT_1_VERIFYING

    def test_valid_transition_with_verification_flags(self):
        result = transition(
            OrderStatus.PAYMENT_1_VERIFYING,
            OrderStatus.PREPARING,
            first_verified=True,
        )
        assert result == OrderStatus.PREPARING

    def test_transition_to_delivered_requires_second_verified(self):
        result = transition(
            OrderStatus.PAYMENT_2_VERIFYING,
            OrderStatus.DELIVERED,
            second_verified=True,
        )
        assert result == OrderStatus.DELIVERED

    def test_invalid_transition_raises(self):
        with pytest.raises(DomainError) as exc:
            transition(OrderStatus.PAYMENT_1_PENDING, OrderStatus.PREPARING)
        assert exc.value.code == "INVALID_STATE_TRANSITION"
        assert exc.value.status == 409

    def test_preparing_without_first_verified_raises(self):
        with pytest.raises(DomainError) as exc:
            transition(OrderStatus.PAYMENT_1_VERIFYING, OrderStatus.PREPARING, first_verified=False)
        assert exc.value.code == "FIRST_PAYMENT_REQUIRED"
        assert exc.value.status == 409

    def test_delivered_without_second_verified_raises(self):
        with pytest.raises(DomainError) as exc:
            transition(
                OrderStatus.PAYMENT_2_VERIFYING, OrderStatus.DELIVERED, second_verified=False
            )
        assert exc.value.code == "SECOND_PAYMENT_REQUIRED"
        assert exc.value.status == 409

    def test_terminal_state_cannot_transition(self):
        with pytest.raises(DomainError) as exc:
            transition(OrderStatus.DELIVERED, OrderStatus.CANCELLED)
        assert exc.value.code == "INVALID_STATE_TRANSITION"

    def test_cancelled_cannot_transition(self):
        with pytest.raises(DomainError) as exc:
            transition(OrderStatus.CANCELLED, OrderStatus.PAYMENT_1_PENDING)
        assert exc.value.code == "INVALID_STATE_TRANSITION"

    def test_full_flow_simulation(self):
        state = transition(OrderStatus.PAYMENT_1_PENDING, OrderStatus.PAYMENT_1_VERIFYING)
        assert state == OrderStatus.PAYMENT_1_VERIFYING

        state = transition(state, OrderStatus.PREPARING, first_verified=True)
        assert state == OrderStatus.PREPARING

        state = transition(state, OrderStatus.READY_FOR_PICKUP)
        assert state == OrderStatus.READY_FOR_PICKUP

        state = transition(state, OrderStatus.ON_THE_WAY)
        assert state == OrderStatus.ON_THE_WAY

        state = transition(state, OrderStatus.ARRIVED_AT_CUSTOMER)
        assert state == OrderStatus.ARRIVED_AT_CUSTOMER

        state = transition(state, OrderStatus.PAYMENT_2_VERIFYING)
        assert state == OrderStatus.PAYMENT_2_VERIFYING

        state = transition(state, OrderStatus.DELIVERED, second_verified=True)
        assert state == OrderStatus.DELIVERED

        with pytest.raises(DomainError):
            transition(state, OrderStatus.CANCELLED)


class TestRetryTransitions:
    def test_payment_1_verifying_back_to_pending(self):
        result = transition(OrderStatus.PAYMENT_1_VERIFYING, OrderStatus.PAYMENT_1_PENDING)
        assert result == OrderStatus.PAYMENT_1_PENDING

    def test_payment_2_verifying_back_to_arrived(self):
        result = transition(OrderStatus.PAYMENT_2_VERIFYING, OrderStatus.ARRIVED_AT_CUSTOMER)
        assert result == OrderStatus.ARRIVED_AT_CUSTOMER

    def test_cancel_from_payment_1_pending(self):
        result = transition(OrderStatus.PAYMENT_1_PENDING, OrderStatus.CANCELLED)
        assert result == OrderStatus.CANCELLED

    def test_cancel_from_payment_1_verifying(self):
        result = transition(OrderStatus.PAYMENT_1_VERIFYING, OrderStatus.CANCELLED)
        assert result == OrderStatus.CANCELLED

    def test_reject_from_payment_1_verifying(self):
        result = transition(OrderStatus.PAYMENT_1_VERIFYING, OrderStatus.REJECTED)
        assert result == OrderStatus.REJECTED

    def test_cancelled_with_refund_from_preparing(self):
        result = transition(OrderStatus.PREPARING, OrderStatus.CANCELLED_WITH_REFUND)
        assert result == OrderStatus.CANCELLED_WITH_REFUND

    def test_cancelled_with_refund_from_ready_for_pickup(self):
        result = transition(OrderStatus.READY_FOR_PICKUP, OrderStatus.CANCELLED_WITH_REFUND)
        assert result == OrderStatus.CANCELLED_WITH_REFUND

    def test_cancelled_with_refund_from_on_the_way(self):
        result = transition(OrderStatus.ON_THE_WAY, OrderStatus.CANCELLED_WITH_REFUND)
        assert result == OrderStatus.CANCELLED_WITH_REFUND

    def test_delivery_failed_from_arrived(self):
        result = transition(OrderStatus.ARRIVED_AT_CUSTOMER, OrderStatus.DELIVERY_FAILED)
        assert result == OrderStatus.DELIVERY_FAILED
