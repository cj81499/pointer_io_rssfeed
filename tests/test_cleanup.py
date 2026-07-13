from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING

import bs4
import pytest

from pointer_io_rssfeed import cleanup

if TYPE_CHECKING:
    from syrupy.assertion import SnapshotAssertion

_FIXTURE_DIR = pathlib.Path(__file__).parent / "fixtures"


@pytest.mark.parametrize(
    "fixture_path",
    sorted(_FIXTURE_DIR.glob("*.html")),
    ids=lambda p: p.name,
)
def test_html_to_description(fixture_path: pathlib.Path, snapshot: SnapshotAssertion) -> None:
    html = fixture_path.read_text()
    description = cleanup.html_to_description(html)
    pretty = bs4.BeautifulSoup(description, features="html.parser").prettify()
    assert pretty == snapshot


@pytest.mark.parametrize(
    "fixture_path",
    sorted(_FIXTURE_DIR.glob("*.html")),
    ids=lambda p: p.name,
)
def test_html_to_description_removes_email_only_markup(fixture_path: pathlib.Path) -> None:
    description = cleanup.html_to_description(fixture_path.read_text())

    assert "style=" not in description
    assert "<table" not in description
    assert "width=" not in description
    assert "_bhlid=" not in description
    assert "&aid=" not in description
    assert "sponsored_ad" not in description
    assert "presented by" not in description.lower()
    assert "promoted by" not in description.lower()
    assert "how did you like this issue" not in description.lower()


@pytest.mark.parametrize(
    ("href", "expected"),
    [
        ("https://example.com/article?aid=abc&keep=yes", "https://example.com/article?keep=yes"),
        ("https://example.com/article#section?&aid=abc", "https://example.com/article#section"),
        (
            "https://example.com/article#section?keep=yes&aid=abc",
            "https://example.com/article#section?keep=yes",
        ),
    ],
)
def test_tracking_parameters_are_removed_from_query_and_fragment(href: str, expected: str) -> None:
    assert cleanup._without_tracking_parameters(href) == expected  # noqa: SLF001


def test_html_to_description_removes_tracking_parameters_from_fragment_urls() -> None:
    description = cleanup.html_to_description(
        """
        <tr id="content-blocks"><td><table><tr><td>
          <p><a href="https://example.com/article#section?keep=yes&amp;aid=abc&amp;_bhlid=def">Article</a></p>
        </td></tr></table></td></tr>
        """
    )

    assert 'href="https://example.com/article#section?keep=yes"' in description
    assert "aid=" not in description
    assert "_bhlid=" not in description


def test_html_to_description_keeps_editorial_subscribe_calls_to_action() -> None:
    description = cleanup.html_to_description(
        "<html><body><p>Subscribe for a weekly roundup of engineering articles.</p></body></html>"
    )

    assert "Subscribe for a weekly roundup of engineering articles." in description


def test_html_to_description_removes_unsubscribe_controls() -> None:
    description = cleanup.html_to_description("<html><body><p>Unsubscribe from this list.</p></body></html>")

    assert description == ""


def test_html_to_description_removes_mailchimp_unsubscribe_footer() -> None:
    description = cleanup.html_to_description(
        '<html><body><div class="mcnTextContent"><a>unsubscribe from this list</a></div></body></html>'
    )

    assert description == ""


def test_html_to_description_keeps_editorial_discussion_of_unsubscribing() -> None:
    description = cleanup.html_to_description(
        """
        <html><body><div class="mcnTextContent">
          <h1>The Monstrosity Email Has Become</h1>
          <p>I unsubscribe from everything that contains an unsubscribe link.</p>
        </div></body></html>
        """
    )

    assert "The Monstrosity Email Has Become" in description
    assert "I unsubscribe from everything" in description


def test_html_to_description_keeps_editorial_images() -> None:
    description = cleanup.html_to_description(
        """
        <html><body>
          <h2>Null Pointer: The Blame Game</h2>
          <img
            src="https://example.com/the-blame-game.png"
            alt="The Blame Game"
            width="650"
            style="display: block"
          >
        </body></html>
        """
    )

    assert '<img alt="The Blame Game" src="https://example.com/the-blame-game.png"/>' in description


def test_html_to_description_keeps_fallback_editorial_content_with_unsubscribe_footer() -> None:
    description = cleanup.html_to_description(
        """
        <html><body>
          <div><h1>When Is Someone Ready To Manage Managers?</h1></div>
          <table><tr><td><p>Update your email preferences or unsubscribe here.</p></td></tr></table>
        </body></html>
        """
    )

    assert "When Is Someone Ready To Manage Managers?" in description
    assert "unsubscribe" not in description.lower()


def test_html_to_description_uses_foundation_email_content_boundary() -> None:
    description = cleanup.html_to_description(
        """
        <html><body>
          <h1>Issue #119.1</h1><nav>Prev Next 1 2 3 4</nav>
          <div class="row collapse mail-text"><h2>Editorial article</h2><p>Useful summary.</p></div>
          <footer>Find us at Pointer.io</footer>
        </body></html>
        """
    )

    assert "Editorial article" in description
    assert "Useful summary." in description
    assert "Issue #119.1" not in description
    assert "Prev Next" not in description
    assert "Find us at Pointer.io" not in description


@pytest.mark.parametrize(
    "text",
    [
        "Thanks for reading. Please complete these 3 questions to give me feedback.",
        "Thanks for reading. As always, fill out this form to give me insights.",
        "Overall feedback is incredibly helpful, so here are 3 short questions.",
        "Message from Pointer: All feedback is welcome by answering these 3 short questions.",
        "A quick message from Pointer: Your feedback is immensely valuable. Here are 3 short questions.",
    ],
)
def test_html_to_description_removes_reader_survey_requests(text: str) -> None:
    assert cleanup.html_to_description(f"<html><body><div>{text}</div></body></html>") == ""


def test_html_to_description_removes_survey_tail_without_removing_editorial_content() -> None:
    description = cleanup.html_to_description(
        """
        <html><body><div>
          <h1>Editorial article</h1>
          <p>Useful summary.</p>
          <hr>
          <p>Message from Pointer</p>
          <p>All feedback is welcome by answering these 3 short questions.</p>
        </div></body></html>
        """
    )

    assert "Editorial article" in description
    assert "Useful summary." in description
    assert "Message from Pointer" not in description
    assert "feedback" not in description.lower()


@pytest.mark.parametrize(
    "href",
    [
        "https://twitter.com/share?url=https://example.com/article",
        "https://x.com/intent/post?url=https://example.com/article",
        "https://www.facebook.com/sharer/sharer.php?u=https://example.com/article",
        "https://www.linkedin.com/sharing/share-offsite/?url=https://example.com/article",
        "https://bsky.app/intent/compose?text=https://example.com/article",
        "https://www.reddit.com/submit?url=https://example.com/article",
    ],
)
def test_html_to_description_removes_social_share_controls(href: str) -> None:
    description = cleanup.html_to_description(
        f"""
        <html><body>
          <h1><a href="https://example.com/article">Editorial article</a></h1>
          <a href="{href}"><img src="https://example.com/share.png" alt="Share on social media"></a>
        </body></html>
        """
    )

    assert "Editorial article" in description
    assert 'href="https://example.com/article"' in description
    assert "share.png" not in description
    assert href not in description


@pytest.mark.parametrize(
    "text",
    [
        "Project Uno curates the best programming content across the web.",
        "Programming content worth reading.",
        "Project Uno Bookmarklet! Sharing articles to Project Uno just got easier.",
        "Project Uno wants a real name. Click here to help decide what we call this thing.",
        "Project Uno has a new name! Introducing Pointer.",
    ],
)
def test_html_to_description_removes_project_uno_promotions(text: str) -> None:
    assert cleanup.html_to_description(f"<html><body><div>{text}</div></body></html>") == ""


def test_html_to_description_keeps_project_uno_article_attribution() -> None:
    description = cleanup.html_to_description(
        """
        <html><body><div>
          <h1>Editorial article</h1>
          <p>Selected by the editor at Project Uno.</p>
        </div></body></html>
        """
    )

    assert "Editorial article" in description
    assert "Selected by the editor at Project Uno." in description


@pytest.mark.parametrize(
    "text",
    [
        "Share top quality programming content with the rest of the community "
        "using the Pointer bookmarklet. Gimme the Bookmarklet",
        "Any and all feedback on Pointer is welcome. Don't be a stranger!",
        "A Reading Club For Software Developers — Sign Up Here",
        "If you're interested in sponsoring Pointer, here's more info or feel free to click reply.",
        "Upcoming Rewards Refer three people to unlock your next reward.",
        "In-house QA can take years to scale. QA Wolf takes weeks. Chat With QA Wolf",
        "Recommended Reading: Quastor Join 30,000 developers. It's Free!",
        "Friday 14th July's issue is presented by Prolific",
        "Release Product Updates More Quickly and Spend Less Time Firefighting with Datadog",
        "A Note From CodeSee: Join the CodeSee Maps beta program today.",
        "A Note From Retool: Retool is the fastest way for developers to build internal tools.",
        "Your engineering expertise is needed to break new ground in AI.",
        "Don't Build Your Own Auth. Try FusionAuth Today.",
        "Subscribe To The Work-Bench Enterprise Weekly",
        "Sign Up to SWLW, A Reading Club for Software Leaders",
        "Quastor: Join 35,000 developers. It's Free!",
        "Leadership in Tech: Join 17,000 engineering leaders for one weekly email.",
        "Share what you're reading with the rest of the community by emailing it to Pointer.",
        "Was this email forwarded to you? Sign up here.",
        "Quick Poll: Please vote yes or no. Click here.",
        "Pointer is looking for a programming-obsessed intern to join the team.",
        "Join Pointer's Talent Collective. Signup To Browse All Our Jobs.",
        "Try CodeSee Now",
        "Try Retool Out For Free",
        "Start Earning. Sign Up To Prolific.",
        "Start For Free Today with FusionAuth",
        "Start For Free Today",
        "Chat With QA Wolf",
        "Signup to the LHV&nbsp;Daily RoundUp to get the latest news on our portfolio companies and tech trends.",
        "Any and all feedback on Pointer&nbsp;is welcome and considered. Don't be a stranger!",
        "Uncubed - Sponsored Need new work? Sign up here.",
        "I'm working on a project to better understand how people connect movement with emotions. Here's a survey.",
        "Follow Pointer on RSS: https://www.pointer.io/rss/",
        "Notable Event Frontier Tech Week Sign Up Now - Use code POINTER$50OFF to save $50",
        "Editorial Note: I'm looking for software engineers who are currently managing or leading a team "
        "to answer one question over email. If you are interested, click reply.",
        "Sign-up for Pointer here",
        "The best startup engineering jobs in NY",
        "Want to connect with 200+ startups? Submit your resume.",
        "Interested in working at a tech startup? Fill your profile and let awesome startups reach out to you.",
        "Searching for your next senior engineering or engineering management role? Learn how Pointer can help.",
        "Notable Job Opportunities: signup to our Talent Collective. Signup To Browse All Our Jobs.",
        "Recommended Reading: Pointer's Collective. Sign Up To Pointer's Collective Here.",
        "I'm researching the value of social connection and isolation. Reply to this email.",
        "Would you signup for a daily version of Pointer? Click Here To Answer.",
        "Open Question: Reply to this email, I'll read all responses.",
        "Editor's Note: I'm experimenting with sending Pointer out twice a week. My door is always open, hit reply.",
        "I would love to chat with you for 20 mins about a project I'm working on. Reply to this email.",
        "Please reply to this email to share feedback or just to say hello.",
        "Share feedback or whatever you are working on, just click reply!",
        "How do you like the new font? Click reply and let us know.",
        "Developer Insights Needed: help us understand your needs. Start Here!",
        "FREE CDN, DNS, SSL, and DDoS Mitigation with Cloudflare. Sign up for free today!",
        "Join 25 million developers. Solve Problems Together With Postman.",
        "Sign Up To Stream Now",
        "Join 41,000+ companies who trust Doppler. Get Started Free.",
        "Data Elixir is an email newsletter for Data Science. Sign Up for Free.",
        "The System Design Newsletter simplifies complex system design case studies. Subscribe now.",
        "High Growth Engineer is a newsletter. Subscribe for free.",
        "Explore The Workspaces Of Creative Individuals. A free weekly newsletter. Subscribe For Free.",
        "Virtual Code AI Summit. Register Here For Free.",
        "Render and OpenAI event. RSVP Here.",
        "Most Popular From Last Issue: Previously featured article.",
        "A Message From Stream: Activate your free Stream Chat trial.",
        "Use POINTER20 for 20% off — CLICK HERE TO LEARN MORE.",
        "We love feedback. Please complete a short survey. CLICK HERE TO START.",
        "Stay Ahead As A Leader In Tech. Level Up is a curated newsletter. Sign Up Now.",
        "Quastor is a free newsletter read by over 60,000 engineering leaders. Subscribe For Free!",
        "Subscribe to the PostHog newsletter.",
        "Join 45,000+ Software Engineers Leveling Up In Their Career.",
        "Pointer is looking for a programming-obsessed&nbsp;intern to join the team.",
        "Pointer is now publishing exclusive content and accepting submissions. Hit us up.",
        "Editor's Note: We're looking for an illustrator. Please reply to this email.",
        "Project Uno&nbsp;Wants a Real Name. Click here to help decide what we call this thing.",
        "Stream Maker Account: free-forever. CLICK HERE TO GET STARTED.",
        "Engineering job opportunities. Click Here To Apply.",
        "Build business software 10x faster with Retool.",
        "Start Using Retool Now",
        "Authentication & User Management For The Modern Web. Get Started With Clerk's Generous Free Tier.",
        "Release At The Speed Of Code. Join The Private Beta. Exclusive For Pointer Subscribers.",
        "Outpace Industry Innovators With The Leading Speech AI. Start Building With 100 Free Hours.",
        "A Free Newsletter Building Product Skills For Engineers. Product for Engineers is PostHog's newsletter.",
        "Workspaces is a free weekly newsletter. Subscribe For Free.",
        "Click Here To Apply",
        "Interested In A New Role? Pointer is curating vetted engineering roles. Click Here To Apply.",
        "Presented By LinearB",
        "Click here for sponsorship details or reply to this email for enquiries.",
        "Feedback // Unsubscribe // Sponsorship",
        "The Ultimate ISO 27001 Guide. Presented by Vanta.",
        "A note from Vanta: Pointer subscribers get $1000 off Vanta.",
        "WorkOS is a developer platform to make your app Enterprise Ready. Make Your App Enterprise Ready.",
        "Goal Setting + ROI Tracking For Software Engineering. LinearB's upcoming workshop. Register Now.",
        "Register Now",
        "Only VC backed companies can hire from our collective. Sign Up To The Collective Here.",
        "Job Product Engineer, Fraud Prevention: Clerk is hiring. Apply Today.",
        "Editor's Note: Thank you for 500 issues! We're looking for feedback. Click reply and let us know!",
        "Notable Event Index Conference. Free community conference. Register Here.",
        "Notable Event AI in Action: Transforming Engineering, Business, And People. Register Here with code POINTER.",
        "Index Conference is a free community conference. Register Here.",
        "Register Here",
        "A Note From Stream: Free Chat & Activity Feed APIs. Activate your free Stream Chat trial.",
        "A Note From Swarmia: start shipping 10x faster. Unlock Your Engineering Metrics Today.",
        "Airplane is a developer platform for building custom internal tools. Get Started For Free!",
        "PostHog is an open source suite of product tools. Get Started Free.",
        "Speakeasy's managed SDK pipeline creates Terraform providers. Join The TF Beta.",
        "Multi is game-changing pair-programming. Join Multi for Free.",
        "Openlayer helps teams test machine learning models. Try It Out For Free.",
        "Product for Engineers is PostHog's newsletter. Subscribe For Free.",
        "Subscribe For Free",
        "Quotient provides engineering productivity insights. Mention Pointer For A Free Month Of Insights.",
        "Please complete a short survey so we can keep improving Pointer for you. Click Here To Start.",
        "Editor's Note: We're looking for feedback on Pointer. Click reply and let us know!",
        "Calling All Developers! Join the Developer Nation Survey. Start Now!",
        "Recommended Reading: Alphalist CTO Newsletter. Subscribe For Free.",
        "Join The Private Beta. Exclusive For Pointer Subscribers.",
        "Get Started For Free!",
        "The Best Pair Programming Tool For MacOS. Multi is a game-changing new way to work on code together.",
        "Openlayer: The Evaluation Workspace For AI. Tired of guessing if your model is good enough?",
        "You Can Join Our Discord Here. Or Try It Out For Free.",
        "Take Action To Build The Most Productive Engineering Teams. Powered by Quotient.",
        "Mention Pointer For A Free Month Of Insights",
    ],
)
def test_html_to_description_removes_newsletter_promotions(text: str) -> None:
    assert cleanup.html_to_description(f"<html><body><div>{text}</div></body></html>") == ""


def test_html_to_description_removes_embedded_signup_without_losing_articles() -> None:
    description = cleanup.html_to_description(
        """
        <html><body><div class="mcnTextContent">
          <div><a>Sign Up Here To Receive Pointer</a></div>
          <h1>Defining a Distinguished Engineer</h1>
          <p>A framework for technical leadership.</p>
        </div></body></html>
        """
    )

    assert "Sign Up Here To Receive Pointer" not in description
    assert "Defining a Distinguished Engineer" in description
    assert "A framework for technical leadership." in description


def test_html_to_description_removes_embedded_signup_link_without_losing_articles() -> None:
    description = cleanup.html_to_description(
        """
        <html><body><div class="mcnTextContent">
          <a>Sign Up Here To Receive Pointer</a><br>
          <h1>How to Build a Successful Team</h1>
        </div></body></html>
        """
    )

    assert "Sign Up Here To Receive Pointer" not in description
    assert "How to Build a Successful Team" in description


def test_html_to_description_removes_embedded_editor_note_without_losing_articles() -> None:
    description = cleanup.html_to_description(
        """
        <html><body><div class="mcnTextContent">
          <h1>First article</h1>
          <table><tr><td>
            <strong>Editor&rsquo;s Note</strong>
            <p>We&rsquo;re testing a new platform to send out Pointer. If you see any issues with this email
            or have any feedback, please click reply and let us know.</p>
          </td></tr></table>
          <h1>Second article</h1>
        </div></body></html>
        """
    )

    assert "Editor\N{RIGHT SINGLE QUOTATION MARK}s Note" not in description
    assert "testing a new platform" not in description
    assert "First article" in description
    assert "Second article" in description


def test_html_to_description_removes_cartoon_feedback_cta_without_losing_cartoon_credit() -> None:
    description = cleanup.html_to_description(
        """
        <html><body><div class="mcnTextContent">
          <img src="https://example.com/cartoon.png" alt="Null Pointer cartoon">
          <p>Hand-drawn by <a href="https://ma.nu/graphics/">Manu</a>.
          Got an idea for a cartoon? Click reply and let us know</p>
        </div></body></html>
        """
    )

    assert "cartoon.png" in description
    assert "Hand-drawn by" in description
    assert "Manu" in description
    assert "Got an idea for a cartoon" not in description


def test_html_to_description_removes_feedback_ps_without_losing_editorial_note() -> None:
    description = cleanup.html_to_description(
        """
        <html><body><div class="mcnTextContent">
          <p><b>Editorial Note</b></p>
          <p>A substantive personal thought worth preserving.</p>
          <p>PS. I'm experimenting with this section to pen personal thoughts.
          Feel free to hit reply and share any feedback.</p>
        </div></body></html>
        """
    )

    assert "A substantive personal thought worth preserving." in description
    assert "experimenting with this section" not in description


def test_html_to_description_removes_recruitment_note_without_losing_surrounding_articles() -> None:
    description = cleanup.html_to_description(
        """
        <html><body><div class="mcnTextContent">
          <h1>Writing Code vs. Shipping Code</h1>
          <table><tr><td>
            <p><b>Editorial Note</b></p>
            <p>I'm looking for software engineers who are currently managing or leading a team
            to answer one question over email.</p>
            <p>If you are interested, click reply.</p>
          </td></tr></table>
          <h1>When Was the Last Time You Did Just One Thing?</h1>
        </div></body></html>
        """
    )

    assert "Writing Code vs. Shipping Code" in description
    assert "When Was the Last Time You Did Just One Thing?" in description
    assert "looking for software engineers" not in description


def test_html_to_description_removes_rating_prompt_without_losing_preceding_articles() -> None:
    description = cleanup.html_to_description(
        """
        <html><body><tr id="content-blocks"><td><table><tbody>
          <tr><td><h1>The Sneaky Costs Of Scaling Serverless</h1><p>Useful summary.</p></td></tr>
          <tr><td><h2>Notable Links</h2><p>ComfyUI: A useful tool.</p></td></tr>
          <tr><td><p>Click the below and shoot me an email!</p></td></tr>
          <tr><td><p>1 = Didn't enjoy it all // 5 = Really enjoyed it</p></td></tr>
          <tr><td><p><a>1</a> … <a>2</a> … <a>3</a> … <a>4</a> … <a>5</a></p></td></tr>
          <tr><td><table><tr><td></td></tr></table></td></tr>
        </tbody></table></td></tr></body></html>
        """
    )

    assert "The Sneaky Costs Of Scaling Serverless" in description
    assert "ComfyUI" in description
    assert "shoot me an email" not in description
    assert "Didn't enjoy it" not in description


def test_html_to_description_removes_embedded_summary_poll_without_losing_articles() -> None:
    description = cleanup.html_to_description(
        """
        <html><body><div class="mcnTextContent">
          <h1>How Is Software Developed At Amazon?</h1>
          <p>Useful summary.</p>
          <div>Are the short summaries (tl;dr sections) helpful? Please vote here</div>
          <h1>A Philosophy of Software Design</h1>
        </div></body></html>
        """
    )

    assert "How Is Software Developed At Amazon?" in description
    assert "A Philosophy of Software Design" in description
    assert "short summaries" not in description


def test_html_to_description_removes_stale_event_calendar() -> None:
    description = cleanup.html_to_description(
        """
        <html><body><div class="mcnTextContent">
          <a href="https://qcon.example">QCon</a> (March 4-6)<br>London, UK
          <a href="https://devnexus.example">DevNexus</a> (March 6-8)<br>Atlanta, USA
          <a href="https://reactday.example">React Day Berlin</a> (Nov 30)<br>Berlin, Germany
        </div></body></html>
        """
    )

    assert description == ""


def test_html_to_description_removes_single_stale_event_calendar_entry() -> None:
    description = cleanup.html_to_description(
        """
        <html><body><div class="mcnTextContent">
          <a href="https://qcon.example">QCon</a> (March 4-6)<br>London, UK
        </div></body></html>
        """
    )

    assert description == ""


def test_html_to_description_removes_stale_event_calendar_with_dates_on_separate_lines() -> None:
    description = cleanup.html_to_description(
        """
        <html><body><div class="mcnTextContent">
          <a href="https://django.example">DjangoCon US</a><br>Sept 22-27<br>San Diego, CA
          <a href="https://reactday.example">React Day Berlin</a><br>Nov 30<br>Berlin, Germany
          <a href="https://dotjs.example">dotJS</a><br>Dec 5-6<br>Paris, France
        </div></body></html>
        """
    )

    assert description == ""


def test_html_to_description_keeps_editorial_text_with_a_single_event_date() -> None:
    description = cleanup.html_to_description(
        "<html><body><p>React Day Berlin (Nov 30) prompted a useful discussion.</p></body></html>"
    )

    assert "prompted a useful discussion" in description


@pytest.mark.parametrize(
    ("href", "text"),
    [
        ("https://goteleport.com/?utm_source=pointer", "Get Started At Goteleport.com"),
        ("https://www.swarmia.com/developers/?utm_source=email", "Try Swarmia For Free"),
        ("https://swarmia.co/3KpsjEP", "Try Swarmia With A Free 14-Day Trial"),
        ("https://www.datadoghq.com/free-trial/?utm_source=pointer", "Try Datadog For Free"),
        ("https://www.influxdata.com/lp/why-influxdb-cloud/?utm_source=vendor", "Try For Free"),
        ("https://www.qawolf.com/?utm_source=pointer", "Schedule A Demo To Learn More"),
        ("https://go.clerk.com/t3r2g6F", "Try Clerk - Start With Our Free Tier"),
        ("https://www.speakeasy.com/?utm_source=pointer-aug", "Try For Free"),
    ],
)
def test_html_to_description_removes_known_sponsor_blocks(href: str, text: str) -> None:
    description = cleanup.html_to_description(
        f'<html><body><div class="mcnTextContent"><a href="{href}">{text}</a></div></body></html>'
    )

    assert description == ""


def test_html_to_description_removes_split_sponsor_card_without_losing_article() -> None:
    description = cleanup.html_to_description(
        """
        <html><body>
          <div class="mceText">Tuesday 7th March's issue is presented by ExampleCo</div>
          <div class="mceText">ExampleCo helps teams ship faster with a commercial platform.</div>
          <div class="mceText"><a href="https://example.com/demo">Get Started Now</a></div>
          <div class="mceText"><a href="https://editorial.example/article">A Legitimate Engineering Article</a></div>
        </body></html>
        """
    )

    assert "ExampleCo helps teams" not in description
    assert "Get Started Now" not in description
    assert "A Legitimate Engineering Article" in description


def test_html_to_description_keeps_article_immediately_after_two_block_sponsor_card() -> None:
    description = cleanup.html_to_description(
        """
        <html><body>
          <div class="mceText">Tuesday 14th February's issue is presented by WorkOS</div>
          <div class="mceText">WorkOS is a developer platform to make your app Enterprise Ready.</div>
          <div class="mceText">
            <a href="https://lethain.com/eng-strategies/">Writing An Engineering Strategy</a>
            <p>Will discusses an example engineering strategy.</p>
          </div>
        </body></html>
        """
    )

    assert "WorkOS" not in description
    assert "Writing An Engineering Strategy" in description
    assert "Will discusses" in description


@pytest.mark.parametrize(
    "cta",
    [
        "Make Your App Enterprise Ready",
        "Solve Problems Together With Postman",
        "Build For Free Today",
        "Explore DEPT Digital Products",
        "Got A Game-Changing Idea? Apply Here Today",
        "Free One Month Trial And Direct Support On Slack",
        "Stop Waiting, Start Securing Your Code Today For Free",
        "Check Out OneSchema Here",
        "Read More On The WorkOS Blog",
        "Future-Proof Your Auth Stack With WorkOS",
        "Ship SSO This Afternoon",
    ],
)
def test_html_to_description_removes_split_sponsor_cta_variants(cta: str) -> None:
    description = cleanup.html_to_description(
        f"""
        <html><body>
          <div class="mceText">Tuesday's issue is presented by ExampleCo</div>
          <div class="mceText">ExampleCo provides a commercial developer platform.</div>
          <div class="mceText"><a href="https://example.com/offer">{cta}</a></div>
          <div class="mceText">A legitimate article</div>
        </body></html>
        """
    )

    assert cta not in description
    assert "A legitimate article" in description


def test_html_to_description_removes_later_article_on_same_issue_sponsor_domain() -> None:
    description = cleanup.html_to_description(
        """
        <html><body>
          <div class="mceText">Tuesday's issue is presented by Cast AI</div>
          <div class="mceText"><a href="https://cast.ai/product">Cast AI saves cloud costs.</a></div>
          <div class="mceText"><a href="https://cast.ai/demo">Get Started</a></div>
          <div class="mceText"><a href="https://editorial.example/one">First legitimate article</a></div>
          <div class="mceText"><a href="https://editorial.example/two">Second legitimate article</a></div>
          <div class="mceText"><a href="https://cast.ai/blog/spot-pricing">The Rise And Fall Of Spot Pricing</a>
          <p>Our game-changing tool can save you big bucks. Don't miss out.</p></div>
          <div class="mceText"><a href="https://editorial.example/three">Third legitimate article</a></div>
        </body></html>
        """
    )

    assert "Cast AI saves cloud costs" not in description
    assert "The Rise And Fall Of Spot Pricing" not in description
    assert "First legitimate article" in description
    assert "Second legitimate article" in description
    assert "Third legitimate article" in description


def test_html_to_description_removes_empty_anchors_but_keeps_text_and_image_links() -> None:
    description = cleanup.html_to_description(
        """
        <html><body><div class="mcnTextContent">
          <a href="https://empty.example"><strong>  </strong></a>
          <a href="https://article.example">A real article</a>
          <a href="https://image.example"><img src="https://example.com/article.png" alt="Article image"></a>
        </div></body></html>
        """
    )

    assert "empty.example" not in description
    assert '<a href="https://article.example">A real article</a>' in description
    assert (
        '<a href="https://image.example"><img alt="Article image" src="https://example.com/article.png"/></a>'
        in description
    )


def test_html_to_description_keeps_editorial_article_on_known_sponsor_host() -> None:
    description = cleanup.html_to_description(
        """
        <html><body><div class="mcnTextContent">
          <a href="https://www.datadoghq.com/blog/tagging-best-practices/">
            Best Practices For Tagging Your Infrastructure And Applications
          </a>
          <p>Tagging is important for monitoring application data in modern environments.</p>
        </div></body></html>
        """
    )

    assert "Best Practices For Tagging" in description
    assert "Tagging is important" in description


def test_html_to_description_removes_wealthfront_promotion_disclosure() -> None:
    description = cleanup.html_to_description(
        """
        <html><body><div class="mcnTextContent"><h6>
          The APY reflects the weighted average of deposit balances at participating Program Banks.
          Wealthfront Brokerage sweeps cash balances to Program Banks, where they earn the variable APY.
          If you are eligible for the overall boosted rate of 4.05% offered in connection with this promo,
          your boosted rate is also subject to change.
        </h6></div></body></html>
        """
    )

    assert description == ""


@pytest.mark.parametrize(
    "text",
    [
        (
            "LHV invests in early stage startups across all sectors including emerging technologies, "
            "enterprise and consumer. If you or someone you know is working on a startup, email us."
        ),
        "If you're interested in mentoring people of color & under-represented minorities, signup here.",
        (
            "Notable Event Level Up Your Engineering Leadership With LeadDev. Join a community of software "
            "engineering leaders this October 15\N{EN DASH}17 in New York. Three events, one week. Learn more."
        ),
    ],
)
def test_html_to_description_removes_remaining_non_editorial_solicitations(text: str) -> None:
    assert cleanup.html_to_description(f'<html><body><div class="mcnTextContent">{text}</div></body></html>') == ""


def test_html_to_description_removes_embedded_submission_note_without_losing_article() -> None:
    description = cleanup.html_to_description(
        """
        <html><body><div class="mcnTextContent">
          <p>{Ed. Note: Pointer is publishing exclusive content! We're currently accepting submissions,
          so if you're interested in writing, hit us up at share@pointer.io.}</p>
          <h1>Pointer Exclusive — 5 Mistakes We've Made Scaling Our Engineering Team</h1>
          <p>Legitimate article summary.</p>
        </div></body></html>
        """
    )

    assert "currently accepting submissions" not in description
    assert "5 Mistakes We've Made" in description
    assert "Legitimate article summary" in description


def test_html_to_description_removes_split_node_submission_note_without_losing_article() -> None:
    description = cleanup.html_to_description(
        """
        <html><body><div class="mcnTextContent"><div>
          <span>{Ed. Note: Pointer is publishing exclusive content! W</span>
          <span>e're currently accepting submissions, so if you're interested in writing, h</span>
          <span>it us up at share@pointer.io.}</span><br>
          <div><h1>5 Mistakes We've Made Scaling Our Engineering Team</h1></div>
          <div>Legitimate article summary.</div>
        </div></div></body></html>
        """
    )

    assert "currently accepting submissions" not in description
    assert "5 Mistakes We've Made" in description
    assert "Legitimate article summary" in description


@pytest.mark.parametrize(
    "text",
    [
        (
            "Interested in working at an early stage startup? Fill your profile and let startups reach out to you. "
            "Start Now."
        ),
        "Recommended Jobs Through My Network: Graphy is hiring software engineers.",
        "A Note From HubSpot: We're growing our engineering team. Check out our open roles.",
        "A Note From Hex: Build the future of collaborative analytics. Check It Out.",
        "A Note From Mattermost. Mattermost is a collaboration platform built for developers. Try Mattermost Now.",
        (
            "3x Faster Visual Reviews For Engineering Teams. BrowserStack's Visual Review Agent helps teams "
            "ship confidently. Get started."
        ),
        (
            "The A11y Testing Gap: Why 40% Of Issues Still Need Manual Review. "
            "Run a free scan to see what automated tools miss!"
        ),
        (
            "Editorial Note I'll be in New York on September 15-16 for LeadDev's LDX3. "
            "If you're going, hit reply and say hi."
        ),
    ],
)
def test_html_to_description_removes_iteration_ten_promotions(text: str) -> None:
    assert cleanup.html_to_description(f'<html><body><div class="mcnTextContent">{text}</div></body></html>') == ""


def test_html_to_description_removes_talent_tracker_technical_challenge_variant() -> None:
    description = cleanup.html_to_description(
        """
        <html><body><div class="mcnTextContent">
          <a href="http://www.lhvtalenttracker.com/?source=7">
            Interested in the technical challenge of an early stage startup?
          </a>
          <a href="http://www.lhvtalenttracker.com/?source=7">Start Now</a>
        </div></body></html>
        """
    )

    assert description == ""


def test_html_to_description_removes_legacy_job_board_after_header() -> None:
    description = cleanup.html_to_description(
        """
        <html><body>
          <div class="mcnTextContent"><h1>Ten Good Rules for Bad APIs</h1></div>
          <div class="mcnTextContent">The Best Startups Engineering Jobs in NY... DATA SCIENCE (based in NY)</div>
          <div class="mcnTextContent">DATA SCIENCE — Example startup is hiring.</div>
          <div class="mcnTextContent">SOFTWARE ENGINEER — Another startup is hiring.</div>
        </body></html>
        """
    )

    assert "Ten Good Rules for Bad APIs" in description
    assert "Best Startups Engineering Jobs" not in description
    assert "DATA SCIENCE" not in description
    assert "SOFTWARE ENGINEER" not in description


def test_html_to_description_starts_job_board_cutoff_at_standalone_header() -> None:
    description = cleanup.html_to_description(
        """
        <html><body>
          <div class="mcnTextContent">
            This edition contains an exclusive article and The Best Startups Engineering Jobs in NY.
          </div>
          <div class="mcnTextContent"><h1>Ten Good Rules for Bad APIs</h1></div>
          <div class="mcnTextContent">The Best Startups Engineering Jobs in NY</div>
          <div class="mcnTextContent">SOFTWARE ENGINEER — Example startup is hiring.</div>
        </body></html>
        """
    )

    assert "Ten Good Rules for Bad APIs" in description
    assert "SOFTWARE ENGINEER" not in description


def test_html_to_description_removes_headerless_job_board_after_exclusive_article() -> None:
    description = cleanup.html_to_description(
        """
        <html><body>
          <div class="mcnTextContent">
            Introducing Pointer's Friday edition, featuring an exclusive article plus
            the best startup engineering jobs in NY.
          </div>
          <div class="mcnTextContent"><h1>Ten Good Rules for Bad APIs</h1></div>
          <div class="mcnTextContent">DATA SCIENCE (based in NY)</div>
          <div class="mcnTextContent">Data Engineer @ Buzzfeed</div>
          <div class="mcnTextContent">SOFTWARE ENGINEER (based in NY)</div>
        </body></html>
        """
    )

    assert "Ten Good Rules for Bad APIs" in description
    assert "DATA SCIENCE" not in description
    assert "Data Engineer @ Buzzfeed" not in description
    assert "SOFTWARE ENGINEER" not in description


@pytest.mark.parametrize(
    ("header", "body"),
    [
        ("Most Popular From Last Issue", "Managing Up: 11 Ways To Get Better Feedback"),
        ("Notable Event", "See How Search And AI Applications Are Built At Scale At Index 2024"),
        ("Developer Insights Needed", "We Need Your Coding Intellect. Start Here!"),
    ],
)
def test_html_to_description_removes_split_heading_and_body_without_losing_article(header: str, body: str) -> None:
    description = cleanup.html_to_description(
        f"""
        <html><body>
          <div class="mceText">First legitimate article</div>
          <div class="mceText">{header}</div>
          <div class="mceText">{body}</div>
          <div class="mceText">Next legitimate article</div>
        </body></html>
        """
    )

    assert header not in description
    assert body not in description
    assert "First legitimate article" in description
    assert "Next legitimate article" in description


def test_html_to_description_removes_embedded_wildcard_hiring_cta_without_losing_article() -> None:
    description = cleanup.html_to_description(
        """
        <html><body><div class="mcnTextContent">
          <h1>Building An Effective Technical Interview Process</h1>
          <p>Legitimate article summary.</p>
          <a href="https://trywildcard.com/team">Wildcard is Hiring</a>
        </div></body></html>
        """
    )

    assert "Wildcard is Hiring" not in description
    assert "Building An Effective Technical Interview Process" in description
    assert "Legitimate article summary" in description


def test_html_to_description_removes_embedded_illustrator_prompt_without_losing_articles() -> None:
    description = cleanup.html_to_description(
        """
        <html><body><div class="mceText">
          <h1>First legitimate article</h1>
          <div><b>Editor's Note</b><p>If anyone you are an illustrator, or you know someone talented,
          please reply to this email as we're looking for someone to work on a small project.</p></div>
          <h1>Second legitimate article</h1>
        </div></body></html>
        """
    )

    assert "First legitimate article" in description
    assert "Second legitimate article" in description
    assert "illustrator" not in description
    assert "please reply" not in description


def test_html_to_description_removes_standalone_community_reply_solicitation() -> None:
    description = cleanup.html_to_description(
        """
        <html><body><div class="mcnTextContent">
          <b>An Editorial Note</b> Indeed these are difficult times.
          If there are other helpful resources I can share with the community, please let me know.
          Even if you feel like saying hello, hit reply.
        </div></body></html>
        """
    )

    assert description == ""


def test_html_to_description_removes_future_cartoon_prompt_without_losing_cartoon() -> None:
    description = cleanup.html_to_description(
        """
        <html><body><div class="mceText">
          <h1>Null Pointer</h1><img src="https://example.com/cartoon.png">
          <p>A cartoon about debugging.</p>
          <p>If have you have ideas for future cartoons, hit reply and let us know!</p>
        </div></body></html>
        """
    )

    assert "Null Pointer" in description
    assert "cartoon.png" in description
    assert "A cartoon about debugging" in description
    assert "ideas for future cartoons" not in description


def test_html_to_description_removes_orphan_jobs_header_without_losing_article() -> None:
    description = cleanup.html_to_description(
        """
        <html><body>
          <div class="mceText"><strong>Jobs</strong></div>
          <div class="mceText">Interested In A New Role? Click Here To Apply.</div>
          <div class="mceText">A legitimate article</div>
        </body></html>
        """
    )

    assert "Jobs" not in description
    assert "Click Here To Apply" not in description
    assert "A legitimate article" in description


def test_html_to_description_removes_orphan_recommended_reading_header() -> None:
    description = cleanup.html_to_description(
        """
        <html><body>
          <div class="mceText"><strong>Recommended Reading</strong></div>
          <div class="mceText">Quastor is a free newsletter for engineering leaders. Subscribe For Free!</div>
          <div class="mceText"><strong>Notable Links</strong></div>
          <div class="mceText">A useful open source project.</div>
        </body></html>
        """
    )

    assert "Recommended Reading" not in description
    assert "Quastor" not in description
    assert "Notable Links" in description
    assert "A useful open source project" in description


@pytest.mark.parametrize(
    "text",
    [
        "This issue is presented by Example Corp.",
        "This article is promoted by Example Corp.",
        "This article is sponsored by Example Corp.",
        "Find a job with Example Corp. #Sponsored",
    ],
)
def test_html_to_description_removes_advertisement_labels(text: str) -> None:
    description = cleanup.html_to_description(f"<html><body><p>{text}</p></body></html>")

    assert description == ""


def test_html_to_description_keeps_presenter_credits_in_editorial_titles() -> None:
    description = cleanup.html_to_description(
        """
        <html><body><div class="mcnTextContent">
          <h1>Requests, PyCon and Python's Future (Podcast) - Presented by Kenneth Reitz</h1>
          <p>A discussion about the future of Python.</p>
        </div></body></html>
        """
    )

    assert "Presented by Kenneth Reitz" in description
    assert "A discussion about the future of Python." in description


def test_html_to_description_removes_article_with_standalone_advertiser_credit() -> None:
    description = cleanup.html_to_description(
        """
        <html><body><div class="mcnTextContent">
          <h1>Tales Of Regret From Onboarding</h1>
          <p>A collection of codebase onboarding stories.</p>
          <em>Presented by CodeSee.</em>
        </div></body></html>
        """
    )

    assert description == ""


def test_html_to_description_removes_block_with_sponsor_tracking_link() -> None:
    description = cleanup.html_to_description(
        """
        <html><body><div class="mcnTextContent">
          <h1><a href="https://example.com/?utm_source=sponsor">Sponsor offer</a></h1>
          <p>Start using the product now.</p>
        </div></body></html>
        """
    )

    assert description == ""


def test_html_to_description_keeps_editorial_link_with_pointer_tracking() -> None:
    description = cleanup.html_to_description(
        """
        <html><body><div class="mcnTextContent">
          <h1><a href="https://example.com/article?utm_source=pointer">Editorial article</a></h1>
          <p>Useful summary.</p>
        </div></body></html>
        """
    )

    assert "Editorial article" in description
    assert "Useful summary." in description
