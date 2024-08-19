import math

from flask import render_template, make_response, request
from slugify import UniqueSlugify

from routes import content_col, routes
from urllib.parse import urlparse


def my_unique_check(text, uids):
    if text in uids:
        return False
    return not content_col.find({"slug": text}).count() > 0


def get_slug(slug):
    custom_slugify_unique = UniqueSlugify(unique_check=my_unique_check, to_lower=True)
    return custom_slugify_unique(slug)


@routes.route('/sitemap')
def get_sitemaps():
    content_count = content_col.count_documents({"status": {"$ne": "Withdrawn"}})
    # Since an xml file can only index 50,000. This way, we will be able to index 2,500,000,000 posts
    bundle_count = math.ceil(content_count / 50000)

    if bundle_count > 50000:
        bundle_count = 50000

    host_components = urlparse(request.host_url)
    host_base = host_components.scheme + "://" + host_components.netloc

    sitemap_template = render_template('sitemap_index.xml', pages=bundle_count, base_url=host_base)
    response = make_response(sitemap_template)
    response.headers['Content-Type'] = 'application/xml'
    return response


@routes.route('/sitemap/<page>')
def get_each_sitemaps(page):
    per_page = 50000
    page = int(page)
    all_content = content_col.find({
        "status": {"$ne": "Withdrawn"}
    }).sort("published_at").skip(per_page * (page - 1)).limit(per_page)

    dynamic_urls = list()
    host_base = "https://home_site_base_url"
    for post in all_content:
        if "updated_at" in post:
            time = post["updated_at"]
        else:
            time = post["published_at"]
        url = {
            "loc": f"{host_base}/post/{post['slug']}",
            "lastmod": time
        }
        dynamic_urls.append(url)

    sitemap_template = render_template('sitemap_file.xml', pages=dynamic_urls)
    response = make_response(sitemap_template)
    response.headers['Content-Type'] = 'application/xml'
    return response
