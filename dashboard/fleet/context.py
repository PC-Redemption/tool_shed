from .models import Project


def fleet_navigation(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {"fleet_projects": []}
    return {"fleet_projects": Project.objects.only("id", "name", "attention_state")[:100]}
