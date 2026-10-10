"""English templates driven solely by exact, structured ranking facts."""

from fractions import Fraction

from domain.recommendation_types import ExplanationCode, ExplanationFact


def display_number(value: Fraction, places: int = 2) -> str:
    """Round exact rationals half-even for prose only, without a float conversion."""
    scale = 10**places
    scaled = round(value * scale)
    sign = "-" if scaled < 0 else ""
    whole, tail = divmod(abs(scaled), scale)
    return f"{sign}{whole}.{tail:0{places}d}" if places else f"{sign}{whole}"


def _number(fact: ExplanationFact, key: str) -> Fraction:
    value = fact.values[key]
    if not isinstance(value, Fraction):
        raise TypeError(f"Explanation {key} must retain its exact Fraction value.")
    return value


def render_explanation(facts: tuple[ExplanationFact, ...]) -> str:
    """Render ordered facts; never infer ranking from rounded presentation values."""
    return " ".join(_render(fact) for fact in facts)


def _render(fact: ExplanationFact) -> str:
    code = fact.code
    if code is ExplanationCode.RECOMMENDED:
        return f"Recommended fully assessed route: {fact.route_id}."
    if code is ExplanationCode.BEST_FULLY_ASSESSED_AVAILABLE:
        return f"Best fully assessed available route: {fact.route_id}; only one route is eligible."
    if code is ExplanationCode.ALL_BLOCKED:
        return (
            "No safe route at this departure time and load. Based on the assessed data, "
            "every route has known No Travel evidence."
        )
    if code is ExplanationCode.NO_FULLY_ASSESSED_TRAVELABLE_ROUTE:
        return (
            "No fully assessed travelable route. Incomplete data prevents assessing every option; "
            "blocking is not established for all routes."
        )
    if code is ExplanationCode.ALL_INCOMPLETE:
        return "All routes have incomplete weather data. No route is eligible for recommendation."
    if code is ExplanationCode.PARTIAL_ROUTES:
        count = fact.values["route_count"]
        return f"Only {count} of 3 requested route options are available."
    if code is ExplanationCode.LEAST_BLOCKED_DIAGNOSTIC:
        return (
            f"Least-blocked complete diagnostic: {fact.route_id}; "
            "this route is blocked and is not recommended."
        )
    if code is ExplanationCode.INCOMPLETE_UNRANKED:
        coverage = display_number(_number(fact, "coverage_fraction") * 100, 1)
        unknown = display_number(_number(fact, "unknown_miles"))
        blocked = " Known blocking evidence is retained." if fact.values["known_blocked"] else ""
        return (
            f"Route {fact.other_route_id} is unranked: {coverage}% coverage, "
            f"{unknown} unknown miles; incomplete data makes it ineligible for recommendation."
            f"{blocked}"
        )
    if code is ExplanationCode.ASSESSED_BEFORE_BLOCKED:
        return (
            f"Route {fact.other_route_id} is blocked; fully assessed routes without known blocks "
            "rank before complete blocked routes."
        )
    if code is ExplanationCode.LOWER_PRIORITY_DURATION_CLOSE:
        minutes = display_number(_number(fact, "duration_difference_seconds") / 60)
        return (
            f"Travel times for {fact.route_id} and {fact.other_route_id} "
            f"differ by {minutes} minutes "
            "(within 4 minutes); duration is lower priority and did not decide this comparison."
        )
    if code is ExplanationCode.TIE_BROKEN_BY_ID:
        return (
            f"All numeric ordering criteria for {fact.route_id} and {fact.other_route_id} "
            "are exactly tied; stable geometry identifier order breaks the tie."
        )
    labels = {
        ExplanationCode.NO_TRAVEL_MILES: ("No Travel miles", 2),
        ExplanationCode.SEVERE_MILES: ("Severe miles", 2),
        ExplanationCode.HIGH_MILES: ("High miles", 2),
        ExplanationCode.AVERAGE_RISK: ("average risk", 3),
        ExplanationCode.DURATION: ("travel time in minutes", 2),
    }
    label, places = labels[code]
    divisor = 60 if code is ExplanationCode.DURATION else 1
    winner = display_number(_number(fact, "winner_value") / divisor, places)
    other = display_number(_number(fact, "other_value") / divisor, places)
    precision = " Raw values differ; displayed values are rounded." if winner == other else ""
    return (
        f"Route {fact.route_id} precedes {fact.other_route_id} on {label}: {winner} vs {other}; "
        f"earlier ordering criteria are equal.{precision}"
    )
