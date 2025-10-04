from apps.projects.models import WorkflowTransition


class WorkflowValidator:
    @staticmethod
    def can_transition(issue, to_status):
        if issue.status == to_status:
            return True, "Already in this status"

        transition_exists = WorkflowTransition.objects.filter(
            project=issue.project,
            from_status=issue.status,
            to_status=to_status,
            is_active=True
        ).exists()

        if transition_exists:
            return True, "Transition allowed"

        if to_status.project != issue.project:
            return False, "Target status does not belong to this project"

        return False, f"Cannot transition from '{issue.status.name}' to '{to_status.name}'"

    @staticmethod
    def get_available_transitions(issue):
        return WorkflowTransition.objects.filter(
            project=issue.project,
            from_status=issue.status,
            is_active=True
        ).select_related('to_status')
