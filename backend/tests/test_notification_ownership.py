import pytest

from app.db.database import SessionLocal
from app.models.notification import Notification
from app.models.user import User
from app.services.notification_service import NotificationService


@pytest.fixture(params=["/api", "/api/v1"])
def prefix(request):
    return request.param


@pytest.fixture
def notifications():
    recipients = {201: 1, 202: 2, 203: 3, 204: 4, 205: None}
    with SessionLocal() as db:
        db.add_all([
            Notification(id=notification_id, user_id=user_id,
                         title=f"Notice {notification_id}", message="Private or shared")
            for notification_id, user_id in recipients.items()
        ])
        db.commit()
    return recipients


@pytest.mark.parametrize("user_id,own_id", [(1, 201), (2, 202), (4, 204)])
def test_personal_list_and_count_are_isolated(client, headers, prefix, notifications, user_id, own_id):
    response = client.get(f"{prefix}/notifications", headers=headers(user_id))
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert [item["id"] for item in response.json()["data"]] == [own_id]
    assert response.json()["unread_count"] == 1
    count = client.get(f"{prefix}/notifications/unread-count", headers=headers(user_id))
    assert count.status_code == 200
    assert count.json()["unread_count"] == 1


@pytest.mark.parametrize("user_id,own_id", [(1, 201), (2, 202), (4, 204)])
def test_personal_bulk_actions_only_affect_owner(client, headers, prefix, notifications, user_id, own_id):
    read_response = client.post(f"{prefix}/notifications/read-all", headers=headers(user_id))
    assert read_response.status_code == 200
    assert read_response.json()["updated_count"] == 1
    with SessionLocal() as db:
        assert db.get(Notification, own_id).read is True
        assert all(db.get(Notification, item_id).read is False
                   for item_id in notifications if item_id != own_id)

    clear_response = client.delete(f"{prefix}/notifications", headers=headers(user_id))
    assert clear_response.status_code == 200
    assert clear_response.json()["deleted_count"] == 1
    with SessionLocal() as db:
        assert db.get(Notification, own_id) is None
        assert all(db.get(Notification, item_id) is not None
                   for item_id in notifications if item_id != own_id)


@pytest.mark.parametrize("user_id,own_id", [(1, 201), (2, 202), (4, 204)])
def test_personal_individual_actions_deny_other_recipients(
    client, headers, prefix, notifications, user_id, own_id
):
    for other_id in notifications:
        if other_id == own_id:
            continue
        assert client.patch(f"{prefix}/notifications/{other_id}/read",
                            headers=headers(user_id)).status_code == 404
        assert client.delete(f"{prefix}/notifications/{other_id}",
                             headers=headers(user_id)).status_code == 404
    with SessionLocal() as db:
        assert all(db.get(Notification, item_id).read is False for item_id in notifications)
        assert all(db.get(Notification, item_id) is not None for item_id in notifications)

    response = client.patch(f"{prefix}/notifications/{own_id}/read", headers=headers(user_id))
    assert response.status_code == 200
    assert response.json()["data"]["id"] == own_id
    assert client.delete(f"{prefix}/notifications/{own_id}",
                         headers=headers(user_id)).status_code == 200


def test_admin_feed_includes_shared_but_bulk_actions_only_mutate_own_notifications(
    client, headers, prefix, notifications
):
    admin_headers = headers(1)
    listing = client.get(f"{prefix}/notifications/admin", headers=admin_headers)
    assert listing.status_code == 200
    assert {item["id"] for item in listing.json()["data"]} == {201, 205}
    assert listing.json()["unread_count"] == 1
    assert client.get(f"{prefix}/notifications/admin/unread-count",
                      headers=admin_headers).json()["unread_count"] == 1
    unread = client.get(f"{prefix}/notifications/admin?unread_only=true", headers=admin_headers)
    assert [item["id"] for item in unread.json()["data"]] == [201]

    marked = client.post(f"{prefix}/notifications/admin/read-all", headers=admin_headers)
    assert marked.status_code == 200
    assert marked.json()["updated_count"] == 1
    with SessionLocal() as db:
        assert all(db.get(Notification, item_id).read is False for item_id in (202, 203, 204, 205))

    cleared = client.delete(f"{prefix}/notifications/admin", headers=admin_headers)
    assert cleared.status_code == 200
    assert cleared.json()["deleted_count"] == 1
    with SessionLocal() as db:
        assert db.get(Notification, 201) is None
        assert all(db.get(Notification, item_id) is not None for item_id in (202, 203, 204, 205))


def test_admin_individual_operations_cannot_touch_customer_or_seller(
    client, headers, prefix, notifications
):
    admin_headers = headers(1)
    for item_id in (202, 203, 204):
        assert client.patch(f"{prefix}/notifications/admin/{item_id}/read",
                            headers=admin_headers).status_code == 404
        assert client.delete(f"{prefix}/notifications/admin/{item_id}",
                             headers=admin_headers).status_code == 404
    with SessionLocal() as db:
        assert all(db.get(Notification, item_id).read is False for item_id in (202, 203, 204))

    marked = client.patch(f"{prefix}/notifications/admin/205/read", headers=admin_headers)
    assert marked.status_code == 404
    assert client.delete(f"{prefix}/notifications/admin/205",
                         headers=admin_headers).status_code == 404
    with SessionLocal() as db:
        assert db.get(Notification, 205).read is False
        assert db.get(Notification, 205) is not None


@pytest.mark.parametrize("method,path", [
    ("GET", "/admin"),
    ("GET", "/admin/unread-count"),
    ("PATCH", "/admin/205/read"),
    ("POST", "/admin/read-all"),
    ("DELETE", "/admin/205"),
    ("DELETE", "/admin"),
])
def test_admin_operations_require_admin(client, headers, prefix, notifications, method, path):
    assert client.request(method, f"{prefix}/notifications{path}").status_code == 401
    for user_id in (2, 4):
        assert client.request(method, f"{prefix}/notifications{path}",
                              headers=headers(user_id)).status_code == 403
    with SessionLocal() as db:
        assert all(db.get(Notification, item_id).read is False for item_id in notifications)
        assert all(db.get(Notification, item_id) is not None for item_id in notifications)


def test_service_rejects_missing_recipient_for_bulk_mutations(notifications):
    with SessionLocal() as db:
        with pytest.raises(ValueError):
            NotificationService.mark_all_read(db, user_id=None)
        with pytest.raises(ValueError):
            NotificationService.clear_all(db, user_id=None)
        with pytest.raises(ValueError):
            NotificationService.mark_as_read(db, 202, user_id=None)
        with pytest.raises(ValueError):
            NotificationService.delete_notification(db, 202, user_id=None)
        with pytest.raises(ValueError):
            NotificationService.list_notifications(db, user_id=None)
        with pytest.raises(ValueError):
            NotificationService.get_unread_count(db, user_id=None)
        assert all(db.get(Notification, item_id).read is False for item_id in notifications)
        assert all(db.get(Notification, item_id) is not None for item_id in notifications)


def test_admin_can_create_shared_and_targeted_notices_without_cross_user_mutation(
    client, headers, prefix
):
    admin_headers = headers(1)
    customer_notice = client.post(
        f"{prefix}/notifications",
        json={"user_id": 2, "title": "Customer notice", "message": "Private"},
        headers=admin_headers,
    )
    shared_notice = client.post(
        f"{prefix}/notifications",
        json={"title": "Shared notice", "message": "Operational"},
        headers=admin_headers,
    )
    assert customer_notice.status_code == shared_notice.status_code == 201
    customer_id = customer_notice.json()["data"]["id"]
    shared_id = shared_notice.json()["data"]["id"]
    assert customer_notice.json()["data"]["user_id"] == 2
    assert shared_notice.json()["data"]["user_id"] is None

    assert client.get(f"{prefix}/notifications", headers=headers(2)).json()["data"][0]["id"] == customer_id
    assert client.get(f"{prefix}/notifications", headers=admin_headers).json()["data"] == []
    assert [item["id"] for item in client.get(
        f"{prefix}/notifications/admin", headers=admin_headers
    ).json()["data"]] == [shared_id]

    assert client.post(f"{prefix}/notifications/read-all", headers=admin_headers).json()["updated_count"] == 0
    assert client.delete(f"{prefix}/notifications", headers=admin_headers).json()["deleted_count"] == 0
    assert client.patch(f"{prefix}/notifications/admin/{customer_id}/read",
                        headers=admin_headers).status_code == 404
    assert client.delete(f"{prefix}/notifications/admin/{customer_id}",
                         headers=admin_headers).status_code == 404
    assert client.patch(f"{prefix}/notifications/admin/{shared_id}/read",
                        headers=admin_headers).status_code == 404
    assert client.delete(f"{prefix}/notifications/admin/{shared_id}",
                         headers=admin_headers).status_code == 404
    with SessionLocal() as db:
        assert db.get(Notification, customer_id).read is False
        assert db.get(Notification, shared_id).read is False


def test_shared_notice_stays_read_only_for_multiple_admins(client, headers, prefix, notifications):
    with SessionLocal() as db:
        db.get(User, 3).role = "admin"
        db.commit()

    for admin_id in (1, 3):
        admin_headers = headers(admin_id)
        feed = client.get(f"{prefix}/notifications/admin", headers=admin_headers)
        assert feed.status_code == 200
        assert 205 in {item["id"] for item in feed.json()["data"]}
        assert feed.json()["unread_count"] == 1
        assert client.patch(f"{prefix}/notifications/admin/205/read",
                            headers=admin_headers).status_code == 404
        assert client.delete(f"{prefix}/notifications/admin/205",
                             headers=admin_headers).status_code == 404
    with SessionLocal() as db:
        assert db.get(Notification, 205).read is False
