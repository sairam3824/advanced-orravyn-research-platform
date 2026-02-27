from .models import Notification


def create_notification(user, notification_type, title, message, link=''):
    """Helper function to create notifications"""
    return Notification.objects.create(
        user=user,
        notification_type=notification_type,
        title=title,
        message=message,
        link=link
    )


def notify_followers(user, notification_type, title, message, link=''):
    """Notify all followers of a user"""
    from apps.accounts.models import UserFollow
    
    followers = UserFollow.objects.filter(following=user).select_related('follower')
    
    notifications = []
    for follow in followers:
        notifications.append(
            Notification(
                user=follow.follower,
                notification_type=notification_type,
                title=title,
                message=message,
                link=link
            )
        )
    
    if notifications:
        Notification.objects.bulk_create(notifications)
    
    return len(notifications)
