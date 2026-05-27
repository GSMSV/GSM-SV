# Notification Read-All Persistence Fix

## Summary

Opening the notification dropdown calls `POST /api/v1/notifications/read-all` through the frontend notification context. The frontend expects this endpoint to mark notifications as read, keep them in the list, then refetch. The backend currently deletes all notifications for the user, so notifications briefly appear from optimistic cache and disappear after the query invalidates.

## Requirements

- `POST /api/v1/notifications/read-all` must mark the current user's unread notifications as read.
- The endpoint must not delete notification rows.
- The frontend "모두 읽음" action must mark local in-memory notifications as read instead of clearing them.
- The endpoint must remain idempotent when all notifications are already read.
- Single-notification deletion via `DELETE /api/v1/notifications/{id}` remains the explicit delete path.
- No API shape change is required.

## Data Model

No schema changes. Reuse `Notification.is_read`.

## API Behavior

- Request: authenticated `POST /api/v1/notifications/read-all`
- Response: unchanged, `{"success": true}`
- Side effect: update rows where `user_id == current_user.id` and `is_read == False` to `is_read=True`

## Frontend Behavior

- Opening the notification menu marks local and remote notifications as read.
- Clicking "모두 읽음" does the same and keeps notification entries visible.
- Clicking "삭제" remains the only per-notification removal action in the menu.

## Security

The endpoint keeps using `Depends(get_current_user)` and scopes updates to `current_user.id`.

## Tests

- Add a route-level test proving `read-all` does not delete rows and marks both unread notifications as read.
- Existing single delete behavior is unchanged.
