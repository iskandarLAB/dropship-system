def stock_freshness(request):
    """Expose stock freshness to every template for logged-in users."""
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {}
    from .services import freshness_summary

    return {"stock_freshness": freshness_summary()}
