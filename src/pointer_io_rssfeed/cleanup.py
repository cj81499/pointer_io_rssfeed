import bs4


def html_to_description(html: str) -> str:
    soup = bs4.BeautifulSoup(html, features="html.parser")

    # TODO: remove stuff after "Notable links"
    # TODO: remove ads
    # TODO: remove header eg: "Friday 5th December issue is presented by Augment Code"
    return str(soup.find("tr", id="content-blocks"))
