import pytest
from services import user_service
from services.auth_service import verify_password
from exceptions import ConflictError, ValidationError, NotFoundError


async def test_create_user_sets_force_password_change(analytics_session):
    user = await user_service.create_user(
        analytics_session, "exec@co.com", "Exec", "Temp@1234", created_by_id=1
    )
    assert user.id is not None
    assert user.force_password_change is True
    assert user.is_active is True
    assert user.is_superuser is False
    assert verify_password("Temp@1234", user.password_hash)


async def test_duplicate_email_raises_conflict(analytics_session):
    await user_service.create_user(analytics_session, "dup@co.com", "A", "pw12345678", created_by_id=1)
    with pytest.raises(ConflictError):
        await user_service.create_user(analytics_session, "dup@co.com", "B", "pw12345678", created_by_id=1)


async def test_cannot_deactivate_self(analytics_session):
    user = await user_service.create_user(analytics_session, "self@co.com", "S", "pw12345678", created_by_id=1)
    with pytest.raises(ValidationError):
        await user_service.deactivate_user(analytics_session, user.id, requesting_user_id=user.id)


async def test_deactivate_missing_user_raises_not_found(analytics_session):
    with pytest.raises(NotFoundError):
        await user_service.deactivate_user(analytics_session, 9999, requesting_user_id=1)


async def test_deactivate_then_reactivate(analytics_session):
    user = await user_service.create_user(analytics_session, "toggle@co.com", "T", "pw12345678", created_by_id=1)
    deactivated = await user_service.deactivate_user(analytics_session, user.id, requesting_user_id=999)
    assert deactivated.is_active is False
    reactivated = await user_service.reactivate_user(analytics_session, user.id)
    assert reactivated.is_active is True


async def test_reset_password_forces_change(analytics_session):
    user = await user_service.create_user(analytics_session, "rp@co.com", "R", "pw12345678", created_by_id=1)
    await user_service.change_own_password(analytics_session, user.id, "NewPass@123")
    assert user.force_password_change is False
    await user_service.reset_password(analytics_session, user.id, "Reset@1234")
    assert user.force_password_change is True
    assert verify_password("Reset@1234", user.password_hash)
