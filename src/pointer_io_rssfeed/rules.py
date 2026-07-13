"""Identify and remove non-editorial content from Pointer archive blocks."""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlsplit

import bs4

_UNWANTED_TEXT = re.compile(
    r"""
    (?:
        # Advertisements and sponsorships.
        \A presented\s+by\s+[\w.-]+ \Z
      | \b issue[ ]is[ ]presented[ ]by \b
      | \b (?:this[ ]issue|issue[ ]\#?\d+) [ ]is[ ]presented[ ]by \b
      | \b (?:promoted|sponsored) [ ]by \b
      | \# sponsored \b
      | sponsored[ ]message
      | release[ ]product[ ]updates[ ]more[ ]quickly.*datadog
      | a[ ]note[ ]from[ ](?:codesee|retool)
      | a\s+note\s+from\s+(?:stream|swarmia)
      | your[ ]engineering[ ]expertise[ ]is[ ]needed[ ]to[ ]break[ ]new[ ]ground[ ]in[ ]ai
      | don.t[ ]build[ ]your[ ]own[ ]auth.*fusionauth
      | (?:try[ ]codesee[ ]now|try[ ]retool[ ]out[ ]for[ ]free)
      | start[ ]earning.*sign[ ]up[ ]to[ ]prolific
      | start[ ]for[ ]free[ ]today.*fusionauth
      | \A start[ ]for[ ]free[ ]today \Z
      | chat[ ]with[ ]qa[ ]wolf
      | a\s+message\s+from
      | pointer20.*20%\s+off
      | stream\s+maker\s+account.*free-forever
      | build\s+business\s+software\s+10x\s+faster\s+with\s+retool
      | \A start\s+using\s+retool\s+now \Z
      | authentication\s+&\s+user\s+management\s+for\s+the\s+modern\s+web
      | release\s+at\s+the\s+speed\s+of\s+code
      | outpace\s+industry\s+innovators\s+with\s+the\s+leading\s+speech\s+ai
      | sponsorship\s+details
      | feedback\s*//\s*unsubscribe\s*//\s*sponsorship
      | ultimate\s+iso\s+27001\s+guide.*presented\s+by\s+vanta
      | a\s+note\s+from\s+vanta
      | a\s+note\s+from\s+(?:hubspot|hex|mattermost)
      | workos\s+is\s+a\s+developer\s+platform.*enterprise\s+ready
      | goal\s+setting\s+\+\s+roi\s+tracking\s+for\s+software\s+engineering
      | \A register\s+now \Z
      | airplane\s+is\s+a\s+developer\s+platform.*custom\s+internal\s+tools
      | posthog\s+is\s+an?\s+open\s+source\s+suite\s+of\s+product\s+tools
      | speakeasy.s\s+managed\s+sdk\s+pipeline
      | multi\s+is\s+game-changing\s+pair-programming
      | openlayer.*try\s+it\s+out\s+for\s+free
      | quotient.*free\s+month\s+of\s+insights
      | \A get\s+started\s+for\s+free!? \Z
      | multi\s+is\s+a\s+game-changing
      | openlayer:\s+the\s+evaluation\s+workspace\s+for\s+ai
      | join\s+our\s+discord.*try\s+it\s+out\s+for\s+free
      | take\s+action\s+to\s+build\s+the\s+most\s+productive\s+engineering\s+teams
      | \A mention\s+pointer\s+for\s+a\s+free\s+month\s+of\s+insights \Z
      | free\s+cdn,\s+dns,\s+ssl,\s+and\s+ddos\s+mitigation\s+with\s+cloudflare
      | join\s+25\s+million\s+developers.*postman
      | sign\s+up\s+to\s+stream\s+now
      | join\s+41,000\+?\s+companies.*doppler
      | the\s+apy\s+reflects\s+the\s+weighted\s+average
        [\s\S]*wealthfront\s+brokerage[\s\S]*connection\s+with\s+this\s+promo
      | lhv\s+invests\s+in\s+early\s+stage\s+startups.*working\s+on\s+a\s+startup
      | interested\s+in\s+working\s+at\s+(?:an?\s+)?(?:funded\s+)?early\s+stage\s+startup
      | \A recommended\s+jobs(?:\s+through\s+my\s+network)?\b
      | \A a\s+note\s+from\s+[\w.-]+:?.*(?:check\s+(?:it|them)\s+out|open\s+roles)
      | 3x\s+faster\s+visual\s+reviews.*browserstack
      | a11y\s+testing\s+gap.*run\s+a\s+free\s+scan

        # Reader-feedback prompts.
      | how[ ]did[ ]you[ ]like[ ]this[ ]issue
      | any\s+and\s+all\s+feedback\s+on\s+pointer\s+is\s+welcome
      | i.m\s+working\s+on\s+a\s+project\s+to\s+better\s+understand.*movement\s+with\s+emotions
      | researching\s+the\s+value\s+of\s+social\s+connection\s+and\s+isolation
      | would\s+you\s+signup\s+for\s+a\s+daily\s+version\s+of\s+pointer
      | open\s+question.*reply\s+to\s+this\s+email
      | experimenting\s+with\s+sending\s+pointer\s+out\s+twice\s+a\s+week
      | love\s+to\s+chat\s+with\s+you\s+for\s+20\s+mins.*project
      | reply\s+to\s+this\s+email\s+to\s+share\s+feedback
      | share\s+feedback\s+or\s+whatever\s+you\s+are\s+working\s+on.*click\s+reply
      | how\s+do\s+you\s+like\s+the\s+new\s+font
      | developer\s+insights\s+needed
      | love\s+feedback.*short\s+survey
      | looking\s+for\s+an\s+illustrator.*reply\s+to\s+this\s+email
      | thank\s+you\s+for\s+500\s+issues.*looking\s+for\s+feedback
      | complete\s+a\s+short\s+survey.*improving\s+pointer
      | looking\s+for\s+feedback\s+on\s+pointer.*click\s+reply
      | calling\s+all\s+developers.*developer\s+nation\s+survey
      | editorial\s+note.*leaddev.s\s+ldx3.*hit\s+reply\s+and\s+say\s+hi
      | helpful\s+resources\s+i\s+can\s+share\s+with\s+the\s+community
        [\s\S]*saying\s+hello[\s\S]*hit\s+reply

        # Newsletter subscription, sharing, and referral promotions.
      | using[ ]the[ ]pointer[ ]bookmarklet
      | signup\s+to\s+the\s+lhv\s+daily\s+roundup
      | a[ ]reading[ ]club[ ]for[ ]software[ ]developers
      | interested[ ]in[ ]sponsoring[ ]pointer
      | upcoming[ ]rewards
      | pointer[ ]is[ ]emailed[ ]twice[ ]a[ ]week.*\bunsubscribe\b
      | unsubscribe[ ]from[ ]this[ ]list
      | subscribe[ ]to[ ]the[ ]work-bench[ ]enterprise[ ]weekly
      | sign[ ]up[ ]to[ ]swlw
      | quastor.*join[ ]\d[\d,]*[ ]developers.*free
      | leadership[ ]in[ ]tech.*join[ ]\d[\d,]*[ ]engineering[ ]leaders
      | share[ ]what[ ]you.re[ ]reading.*community[ ]by[ ]emailing[ ]it
      | was[ ]this[ ]email[ ]forwarded[ ]to[ ]you
      | quick[ ]poll
      | follow\s+pointer\s+on\s+rss
      | notable\s+event.*(?:register|code\s+pointer|leaddev.*learn\s+more)
      | index\s+conference.*free\s+community\s+conference
      | \A register\s+here \Z
      | data\s+elixir.*email\s+newsletter
      | system\s+design\s+newsletter.*simplifies\s+complex\s+system\s+design
      | high\s+growth\s+engineer.*newsletter
      | (?:explore|discover)\s+the\s+workspaces.*(?:newsletter|subscribe\s+for\s+free)
      | virtual\s+code\s+ai\s+summit
      | render.*openai.*(?:event|rsvp)
      | most\s+popular\s+from\s+last\s+issue
      | level\s+up.*curated\s+newsletter
      | quastor\s+is\s+a\s+free\s+newsletter
      | posthog\s+newsletter
      | free\s+newsletter\s+building\s+product\s+skills\s+for\s+engineers
      | join\s+45,000\+?\s+software\s+engineers.*leveling\s+up
      | workspaces\s+is\s+a\s+free\s+weekly\s+newsletter
      | product\s+for\s+engineers\s+is\s+posthog.s\s+newsletter
      | \A subscribe\s+for\s+free \Z
      | alphalist\s+cto\s+newsletter
      | \A join\s+the\s+private\s+beta.*pointer\s+subscribers\.? \Z
      | interested\s+in\s+mentoring\s+people\s+of\s+color.*under-represented\s+minorities.*signup\s+here

        # Pointer's own non-editorial promotions.
      | pointer\s+is\s+looking\s+for\s+a\s+programming-obsessed\s+intern
      | pointer.s[ ]talent[ ]collective
      | pointer\s+is\s+now\s+publishing\s+exclusive\s+content.*accepting\s+submissions
      | sign-?up\s+for\s+pointer\s+here
      | best\s+startup\s+engineering\s+jobs\s+in\s+ny
      | want\s+to\s+connect\s+with\s+200\+\s+startups
      | interested\s+in\s+working\s+at\s+a\s+tech\s+startup
      | searching\s+for\s+your\s+next\s+senior\s+engineering.*pointer\s+can\s+help
      | signup\s+to\s+our\s+talent\s+collective
      | signup\s+to\s+browse\s+all\s+our\s+jobs
      | pointer.s\s+collective
      | job\s+opportunities.*click\s+here\s+to\s+apply
      | interested\s+in\s+a\s+new\s+role.*click\s+here\s+to\s+apply
      | \A click\s+here\s+to\s+apply \Z
      | only\s+vc\s+backed\s+companies\s+can\s+hire\s+from\s+our\s+collective
      | \A job\s+product\s+engineer.*is\s+hiring.*apply\s+today\.? \Z

        # Unlabelled advertisements and newsletter cross-promotions.
      | in-house[ ]qa[ ]can[ ]take[ ]years[ ]to[ ]scale
      | recommended[ ]reading:[ ]quastor
      | uncubed\s*-[ ]*sponsored

        # Legacy Project Uno branding and promotions.
      | project[ -]uno[ ]curates
      | programming[ ]content[ ]worth[ ]reading
      | project[ ]uno[ ]bookmarklet
      | project\s+uno\s+wants\s+a\s+real\s+name
      | project[ ]uno[ ]has[ ]a[ ]new[ ]name

    )
    """,
    re.IGNORECASE | re.VERBOSE,
)
_READER_SURVEY_TEXT = re.compile(
    r"""
    (?:
        thanks[ ]for[ ]reading
      | overall[ ]feedback[ ]is[ ]incredibly[ ]helpful
      | (?:a[ ]quick[ ])? message[ ]from[ ]pointer .*? (?:feedback|questions|survey)
      | your[ ]feedback[ ]is[ ]immensely[ ]valuable
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)
_READER_SURVEY_START = re.compile(
    r"thanks[ ]for[ ]reading|overall[ ]feedback|message[ ]from[ ]pointer|your[ ]feedback",
    re.IGNORECASE,
)
_KNOWN_SPONSOR_HOSTS = frozenset(
    {
        "datadoghq.com",
        "go.clerk.com",
        "goteleport.com",
        "influxdata.com",
        "lhvtalenttracker.com",
        "qawolf.com",
        "speakeasy.com",
        "speakeasyapi.dev",
        "swarmia.co",
        "swarmia.com",
    }
)
_EVENT_DATE = re.compile(
    r"(?:\(|\b)(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sept?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d",
    re.IGNORECASE,
)
_MINIMUM_EVENT_CALENDAR_ENTRIES = 3
_MAXIMUM_SINGLE_EVENT_ENTRY_LENGTH = 160
_SPONSOR_CALL_TO_ACTION = re.compile(
    r"\A(?:build|check|claim|download|explore|free|future-proof|get|got|join|learn|make|read|register|request|"
    r"save|schedule|see|ship|solve|start|stop|try|unify)\b",
    re.IGNORECASE,
)
_SUBMISSION_NOTE_TEXT = re.compile(
    r"ed\.\s+note.*pointer\s+is\s+publishing\s+exclusive\s+content.*accepting\s+submissions.*h\s*it\s+us\s+up",
    re.DOTALL | re.IGNORECASE,
)
_EMBEDDED_PROMOTION_TEXT = re.compile(
    r"""
    (?:
        sign[ ]up[ ]here[ ]to[ ]receive[ ]pointer
      | editor(?:.s|ial)[ ]note .* testing[ ]a[ ]new[ ]platform[ ]to[ ]send[ ]out[ ]pointer .*
      | editor(?:.s|ial)[ ]note .* looking\s+for\s+software\s+engineers .* one\s+question .* click\s+reply\.?
      | ps\.[ ]i.m[ ]experimenting[ ]with[ ]this[ ]section.*share[ ]any[ ]feedback\.
      | are[ ]the[ ]short[ ]summaries.*please[ ]vote[ ]here
      | wildcard[ ]is[ ]hiring
      | editor.s[ ]note .* illustrator .* please[ ]reply .* small[ ]project\.?
      | if[ ]have[ ]you[ ]have[ ]ideas[ ]for[ ]future[ ]cartoons.*hit[ ]reply.*
      | \{? ed\.[ ]note:?[ ]pointer[ ]is[ ]publishing[ ]exclusive[ ]content
        .* accepting[ ]submissions .* hit[ ]us[ ]up .* \}?
    )
    """,
    re.DOTALL | re.IGNORECASE | re.VERBOSE,
)
_STANDALONE_AD_CREDIT = re.compile(r"presented[ ]by[ ][\w .-]+", re.IGNORECASE)
_EMBEDDED_JUNK_FRAGMENT = re.compile(
    r"\.?\s*got\s+an\s+idea\s+for\s+a\s+cartoon\?.*\Z",
    re.IGNORECASE,
)


def _remove_reader_survey(block: bs4.Tag) -> None:
    """Remove a survey footer without discarding earlier content in its block."""
    if not _READER_SURVEY_TEXT.search(block.get_text(" ", strip=True)):
        return

    marker = block.find(string=_READER_SURVEY_START)
    if marker is None:
        block.clear()
        return

    separator = next((tag for tag in marker.find_all_previous("hr") if block in tag.parents), None)
    if separator is None:
        block.clear()
        return

    for node in [separator, *separator.next_siblings]:
        node.extract()


def _remove_submission_note(block: bs4.Tag) -> None:
    """Remove a span-fragmented editor note before its article content."""
    if not _SUBMISSION_NOTE_TEXT.search(block.get_text(" ", strip=True)):
        return
    separator = block.find("br")
    if not isinstance(separator, bs4.Tag):
        return
    for node in [*separator.previous_siblings, separator]:
        node.extract()


def _remove_social_share_controls(block: bs4.Tag) -> None:
    """Remove links whose destination is a social network's sharing UI."""
    for anchor in block.find_all("a", href=True):
        if _is_social_share_url(str(anchor["href"])):
            anchor.decompose()


def _is_unwanted_block(block: bs4.Tag) -> bool:
    if _UNWANTED_TEXT.search(block.get_text(" ", strip=True)):
        return True
    if _is_event_calendar(block):
        return True
    if _has_sponsor_tracking_link(block):
        return True
    return any(
        _STANDALONE_AD_CREDIT.fullmatch(tag.get_text(" ", strip=True)) for tag in block.find_all(["em", "strong"])
    )


def _has_sponsor_tracking_link(block: bs4.Tag) -> bool:
    block_text = block.get_text(" ", strip=True)
    for anchor in block.find_all("a", href=True):
        parts = urlsplit(str(anchor["href"]))
        host = parts.netloc.casefold().removeprefix("www.")
        if host in _KNOWN_SPONSOR_HOSTS and (parts.query or _SPONSOR_CALL_TO_ACTION.search(block_text)):
            return True
        for _, value in parse_qsl(parts.query):
            if "sponsor" in value.casefold() or "advertisement" in value.casefold():
                return True
    return False


def _is_event_calendar(block: bs4.Tag) -> bool:
    """Identify the repeated, stale conference calendar in legacy issues."""
    text = block.get_text(" ", strip=True)
    links = block.find_all("a")
    event_dates = _EVENT_DATE.findall(text)
    if len(links) >= _MINIMUM_EVENT_CALENDAR_ENTRIES and len(event_dates) >= _MINIMUM_EVENT_CALENDAR_ENTRIES:
        return True
    return (
        bool(event_dates)
        and len(links) == 1
        and block.find("br") is not None
        and len(text) <= _MAXIMUM_SINGLE_EVENT_ENTRY_LENGTH
    )


def _remove_embedded_promotions(block: bs4.Tag) -> None:
    """Remove a promotion nested inside a block that also contains articles."""
    for tag in block.find_all(["a", "div", "p", "table"]):
        if _EMBEDDED_PROMOTION_TEXT.fullmatch(tag.get_text(" ", strip=True)):
            tag.decompose()


def _remove_embedded_junk_fragments(block: bs4.Tag) -> None:
    """Remove boilerplate appended to otherwise useful text nodes."""
    for text in block.find_all(string=_EMBEDDED_JUNK_FRAGMENT):
        text.replace_with(_EMBEDDED_JUNK_FRAGMENT.sub("", text))


def _is_social_share_url(href: str) -> bool:
    parts = urlsplit(href)
    host = parts.netloc.casefold().removeprefix("www.")
    path = parts.path.casefold().rstrip("/")

    return (
        (host in {"twitter.com", "x.com"} and path in {"/share", "/intent/post", "/intent/tweet"})
        or (host == "facebook.com" and path in {"/share.php", "/sharer.php", "/sharer/sharer.php"})
        or (host == "linkedin.com" and path in {"/sharearticle", "/sharing/share-offsite"})
        or (host == "bsky.app" and path == "/intent/compose")
        or (host == "reddit.com" and path == "/submit")
    )


def clean_before_rating_prompt(block: bs4.Tag) -> None:
    """Remove fragments whose matching must precede rating-prompt cleanup."""
    _remove_social_share_controls(block)
    _remove_reader_survey(block)


def clean_after_rating_prompt(block: bs4.Tag) -> None:
    """Remove remaining fragments nested inside an otherwise useful block."""
    _remove_submission_note(block)
    _remove_embedded_junk_fragments(block)
    _remove_embedded_promotions(block)


def is_unwanted_block(block: bs4.Tag) -> bool:
    """Return whether a whole block is non-editorial."""
    return _is_unwanted_block(block)


def is_sponsor_call_to_action(text: str) -> bool:
    """Return whether short text begins like a sponsor call to action."""
    return bool(_SPONSOR_CALL_TO_ACTION.search(text))
