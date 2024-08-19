from inspect import CORO_SUSPENDED
import re

import requests
from flask import jsonify, request, url_for
from bson import json_util, ObjectId
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt, verify_jwt_in_request
import json
import urllib.parse
from routes import author_required, login_required, reviewer_required, routes, now, content_col, drafts_col, old_posts_col, per_page, auth_user_col, admin_required, public_route
from routes.general_methods import check_duplicate_post, check_duplicate_comment, check_duplicate_user, get_user_id, paginate, insert_cookie, \
    read_time_in_minutes, send_notification_message, get_random_reviewers
from routes.seo.main import get_slug
from flask_prometheus import metrics

NOTIFY_URL = "http://notification.phistest.fedgen.net:30790/notify/"

REQUESTS = metrics.counter(
    'http_requests_total', 'Total HTTP requests', labels={'endpoint': '/'}
)
REQUEST_LATENCY = metrics.summary('http_request_latency', 'Time spent processing requests')
OTHER_GAUGE = metrics.gauge('some_gauge', 'Description of the gauge')
MY_HISTOGRAM = metrics.histogram('request_size_histogram', 'Distribution of request sizes')

@routes.route('/')
@REQUEST_COUNT.inc(labels={'endpoint': '/'})  # Increment counter for this endpoint
def index():
    with REQUEST_LATENCY.time():
        return 'Hello, World!'
    
@routes.route('/posts', methods=['GET'])
def get_all_posts():
    page = int(request.args.get("page", 1))

    all_content = content_col.find({
        "status": {"$ne": "Withdrawn"}
    }).sort("published_at", -1).skip(per_page * (page - 1)).limit(per_page)
    content_count = content_col.count_documents({"status": {"$ne": "Withdrawn"}})
    if content_count > 0:
        return paginate(all_content, content_count, ".get_all_posts", page)
    else:
        return jsonify({"ok": False,"message": "No posts yet", "posts": []})

@routes.route('/latest', methods=['GET'])
def get_latest_posts():
    page = int(request.args.get("page", 1))

    all_content = content_col.find({
        "status": {"$ne": "Withdrawn"}
    }, {"body": 0}).sort("published_at").limit(30)
    new_content = content_col.find({
        "status": {"$ne": "Withdrawn"}
    }, {"body": 0}).sort("published_at", -1).limit(5)
    popular_content = content_col.find({
        "status": {"$ne": "Withdrawn"}
    }, {"body": 0}).sort("views", -1).limit(6)
    category_content = content_col.find({
        "status": {"$ne": "Withdrawn"}, "categories": "FEDGEN Trends"
    }, {"body": 0}).sort("views", -1).limit(6)

    content_count = content_col.count_documents({"status": {"$ne": "Withdrawn"}})
    if content_count > 0:
        return jsonify({
            "ok": True,
            "newest": [json.loads(json_util.dumps(content)) for content in all_content],
            "popular": [json.loads(json_util.dumps(content)) for content in popular_content],
            "category": [json.loads(json_util.dumps(content)) for content in category_content],
            "all": [json.loads(json_util.dumps(content)) for content in new_content],
            "live": []
        })
    else:
        return jsonify({"ok": False,"message": "No posts yet", "posts": []})


@routes.route('/liked-posts', methods=['GET'])
@login_required()
def get_liked_posts():
    user_id = get_user_id()
    Liked_post = content_col.find({"likers":{"auth_user_id": user_id}, "status": {"$ne": "Withdrawn"}}).sort("published_at", -1)
    if Liked_post is not None:
        return jsonify({"ok": True, "posts": [json.loads(json_util.dumps(content)) for content in Liked_post]})
    else:
        return jsonify({"ok": False, "posts": []})


@routes.route('/post/<slug>', methods=['GET'])
@public_route()
def get_one_post(slug):
    payload = request.payload
    if payload is not None:
        post = content_col.find_one({"slug": slug})
        Liked = content_col.find_one({"slug": slug, "likers":{"auth_user_id": payload['id']}})
        if Liked is not None:
            isLiked = True
        else:
            isLiked = False
        author_post = content_col.count_documents({"author_id": post["author_id"], "status": {"$ne": "Withdrawn"}})
        content_col.update_one({"slug": slug}, {
            '$set': {
                'views': post['views'] + 1
            }
        })
        # del post['likers']
        del post['reviewers']
        if post:
            return jsonify({"ok": True, "message": json.loads(json_util.dumps(post)), "count": author_post, "isLiked": isLiked, "t":"U"})
        else:
            return jsonify({"ok": False,"message": "Post doesn't exist"})
        
    else:
        post = content_col.find_one({"slug": slug})
        author_post = content_col.count_documents({"author_id": post["author_id"], "status": {"$ne": "Withdrawn"}})
        content_col.update_one({"slug": slug}, {
            '$set': {
                'views': post['views'] + 1
            }
        })
        if post:
            return jsonify({"ok": True, "message": json.loads(json_util.dumps(post)), "count": author_post, "t": "P"})
        else:
            return jsonify({"ok": False,"message": "Post doesn't exist"})
        


@routes.route('/reported-posts', methods=['GET'])
def get_reported_posts():
    page = int(request.args.get("page", 1))

    all_content = content_col.find({"status": "Reported"}).sort("published_at").skip(per_page * (page - 1)).limit(per_page)
    content_count = content_col.count_documents({"status": {"$ne": "Withdrawn"}})
    if content_count > 0:
        return paginate(all_content, content_count, ".get_withdrawn_posts", page)
    else:
        return jsonify({"ok": False,"message": "No posts reported"})


@routes.route('/withdrawn-posts', methods=['GET'])
def get_withdrawn_posts():
    page = int(request.args.get("page", 1))

    all_content = content_col.find({"status": "Withdrawn"}).sort("published_at").skip(per_page * (page - 1)).limit(per_page)
    content_count = content_col.count_documents({"status": {"$ne": "Withdrawn"}})
    if content_count > 0:
        return paginate(all_content, content_count, ".get_withdrawn_posts", page)
    else:
        return jsonify({"ok": False,"message": "No posts withdrawn"})
        
@routes.route('/author-withdrawn-posts', methods=['GET'])
@author_required()
def get_author_withdrawn_posts():
    author_id = get_user_id()
    page = int(request.args.get("page", 1))

    all_content = content_col.find({"author_id": author_id, "status": "Withdrawn"}).sort("published_at").skip(per_page * (page - 1)).limit(per_page)
    content_count = content_col.count_documents({"status": {"$ne": "Withdrawn"}})
    if content_count > 0:
        return paginate(all_content, content_count, ".get_withdrawn_posts", page)
    else:
        return jsonify({"ok": False,"message": "No posts withdrawn"})

@routes.route('/get-declined-posts', methods=['GET'])
@author_required()
def get_declined_posts():
    author_id = get_user_id()
    declined_content = drafts_col.find({"status": "Declined", "author_id": author_id}).sort("declined_at", -1)
    if declined_content is not None:
        return jsonify({"ok": True, "posts": [json.loads(json_util.dumps(content)) for content in declined_content ]})
    else:
        return jsonify({"ok": False,"message": "No posts withdrawn"})


@routes.route('/search/<search_query>', methods=['GET'])
def search_through_posts(search_query):
    page = int(request.args.get("page", 1))

    search_query = urllib.parse.unquote_plus(search_query)
    search_filter = {
        "$text": {
            "$search": search_query
        },
        "status": {"$ne": "Withdrawn"}
    }
    all_content = content_col.find(search_filter).sort("likes").skip(per_page * (page - 1)).limit(per_page)
    content_count = content_col.count_documents(search_filter)
    if content_count > 0:
        links = {
            "self": {"href": url_for(".search_through_posts", search_query=search_query, page=page, _external=True)},
            "last": {
                "href": url_for(
                    ".search_through_posts", search_query=search_query, page=(content_count // per_page) + 1, _external=True
                )
            },
        }
        # Add a 'prev' link if it's not on the first page:
        if page > 1:
            links["prev"] = {
                "href": url_for(".search_through_posts", search_query=search_query, page=page - 1, _external=True)
            }
        # Add a 'next' link if it's not on the last page:
        if page - 1 < content_count // per_page:
            links["next"] = {
                "href": url_for(".search_through_posts", search_query=search_query, page=page + 1, _external=True)
            }
        return jsonify({
            "ok": True,
            "posts": [json.loads(json_util.dumps(content)) for content in all_content],
            "_links": links
        })
    else:
        return jsonify({"ok": False,"posts": [], "message": "No posts returned for this search query"})


@routes.route('/posts-by-category/<category>', methods=['GET'])
def get_posts_by_category(category):
    page = int(request.args.get("page", 1))

    search_filter = {
        "categories": re.compile(category, re.IGNORECASE),
        "status": {"$ne": "Withdrawn"}
    }
    all_content = content_col.find(search_filter).sort("published_at").skip(per_page * (page - 1)).limit(per_page)
    content_count = content_col.count_documents(search_filter)
    if content_count > 0:
        links = {
            "self": {"href": url_for(".get_posts_by_category", category=category, page=page, _external=True)},
            "last": {
                "href": url_for(
                    ".get_posts_by_category", category=category, page=(content_count // per_page) + 1, _external=True
                )
            },
        }
        # Add a 'prev' link if it's not on the first page:
        if page > 1:
            links["prev"] = {
                "href": url_for(".get_posts_by_category", category=category, page=page - 1, _external=True)
            }
        # Add a 'next' link if it's not on the last page:
        if page - 1 < content_count // per_page:
            links["next"] = {
                "href": url_for(".get_posts_by_category", category=category, page=page + 1, _external=True)
            }
        return jsonify({
            "ok": True,
            "posts": [json.loads(json_util.dumps(content)) for content in all_content],
            "_links": links
        })
    else:
        return jsonify({"ok": False, "posts": [], "message": "No posts for this category yet"})


@routes.route('/posts-by-tag/<tag>', methods=['GET'])
def get_posts_by_tag(tag):
    page = int(request.args.get("page", 1))

    search_filter = {
        "tags": re.compile(tag, re.IGNORECASE),
        "status": {"$ne": "Withdrawn"}
    }
    all_content = content_col.find(search_filter).sort("published_at").skip(per_page * (page - 1)).limit(per_page)
    content_count = content_col.count_documents(search_filter)
    if content_count > 0:
        links = {
            "self": {"href": url_for(".get_posts_by_tag", tag=tag, page=page, _external=True)},
            "last": {
                "href": url_for(
                    ".get_posts_by_tag", tag=tag, page=(content_count // per_page) + 1, _external=True
                )
            },
        }
        # Add a 'prev' link if it's not on the first page:
        if page > 1:
            links["prev"] = {
                "href": url_for(".get_posts_by_tag", tag=tag, page=page - 1, _external=True)
            }
        # Add a 'next' link if it's not on the last page:
        if page - 1 < content_count // per_page:
            links["next"] = {
                "href": url_for(".get_posts_by_tag", tag=tag, page=page + 1, _external=True)
            }
        return jsonify({
            "ok": True,
            "posts": [json.loads(json_util.dumps(content)) for content in all_content],
            "_links": links
        })
    else:
        return jsonify({"ok": False, "posts": [], "message": "No posts for this tag yet"})


@routes.route('/posts-by-author/<author_id>', methods=['GET'])
def get_posts_by_author(author_id):
    page = int(request.args.get("page", 1))

    search_filter = {
        "author_id": author_id,
        "status": {"$ne": "Withdrawn"}
    }
    all_content = content_col.find(search_filter).sort("published_at").skip(per_page * (page - 1)).limit(per_page)
    content_count = content_col.count_documents(search_filter)
    if content_count > 0:
        links = {
            "self": {"href": url_for(".get_posts_by_author", author_id=author_id, page=page, _external=True)},
            "last": {
                "href": url_for(
                    ".get_posts_by_author", author_id=author_id, page=(content_count // per_page) + 1, _external=True
                )
            },
        }
        # Add a 'prev' link if it's not on the first page:
        if page > 1:
            links["prev"] = {
                "href": url_for(".get_posts_by_author", author_id=author_id, page=page - 1, _external=True)
            }
        # Add a 'next' link if it's not on the last page:
        if page - 1 < content_count // per_page:
            links["next"] = {
                "href": url_for(".get_posts_by_author", author_id=author_id, page=page + 1, _external=True)
            }
        return jsonify({
            "ok": True,
            "posts": [json.loads(json_util.dumps(content)) for content in all_content],
            "_links": links
        })
    else:
        return jsonify({"ok": False,"posts": [], "message": "No posts for this author yet"})


@routes.route('/publish-post/<draft_id>', methods=['POST'])
@reviewer_required()
def publish_post(draft_id):
    draft_filter = {'_id': ObjectId(draft_id)}
    draft = drafts_col.find_one(draft_filter)
    if draft:
        author_id = draft["author_id"]
        title = draft["title"]
        body = draft["body"]
        metadata = draft["metadata"]
        tags = draft["tags"]
        categories = draft["categories"]
        reviewers = draft["reviewers"]
    else:
        return jsonify({"ok": False,"message": "This draft doesn't exist"})

    # Check if any essential field is empty
    if not title or not body:
        return jsonify({"ok": False,"message": "Please provide all fields"})

    # Check if the article is a duplicate
    if check_duplicate_post(title, body, tags, categories):
        return jsonify({"ok": False,"message": "Article already exists"})

    inserted_id = content_col.insert_one({
        'author_id': author_id,
        'draft_id': draft_id,
        'title': title,
        'body': body,
        'read_time': read_time_in_minutes(body),
        'metadata': metadata,
        'tags': tags,
        'categories': categories,
        'reviewers': reviewers,
        'slug': get_slug(title),
        'status': '',
        'published_at': now.strftime("%Y-%m-%d %H:%M")
    }).inserted_id

    if inserted_id:
        return jsonify({"ok": True,"message": "Successfully inserted", "inserted": str(inserted_id)})
    else:
        return jsonify({"ok": False,"message": "Something went wrong"})



@routes.route('/update-post/<post_id>', methods=['PUT'])
@author_required()
def update_post(post_id):
    author_id = get_user_id()
    post_filter = {'_id': ObjectId(post_id), 'author_id': author_id}

    if request.get_json():
        form_data = request.get_json()
        title = form_data['title']
        body = form_data['body']
        if form_data['tags']:
            tags = form_data['tags']
        else:
            tags = "PHIS"
        if form_data['categories']:
            categories = form_data['categories']
        else:
            categories = "Uncategorized"
    elif request.form:
        title = request.form['title']
        body = request.form['body']
        if request.form['tags']:
            tags = request.form['tags']
        else:
            tags = "PHIS"
        if request.form['categories'] == "":
            categories = request.form['categories']
        else:
            categories = "Uncategorized"

    

    updated_post = content_col.update_one(post_filter, {
        '$set': {
            'title': title,
            'body': body,
            'metadata': [],
            'tags': [s.capitalize() for s in set(tags)],
            'categories': [s.capitalize() for s in set(categories)],
            'status': 'Draft',
            'updated_at': now.strftime("%Y-%m-%d %H:%M:%S")
        }
    }).modified_count

    if updated_post > 0:
        return jsonify({"ok": True, "message": "Successfully updated", "updated": str(updated_post)})
    else:
        return jsonify({"ok": False, "message": "Something went wrong"})

@routes.route('/like-post/<post_id>', methods=['PATCH'])
@login_required()
def like_post(post_id):
    user_id = get_user_id()
    post_filter = {'_id': ObjectId(post_id)}
    post = content_col.find_one(post_filter)
    Liked = content_col.find_one({'_id': ObjectId(post_id), "likers":{"auth_user_id": user_id}})
    if Liked is not None:
        return jsonify({"ok": False,"message": "Already liked"})
    else:
        
        updated = content_col.update_one(post_filter, {
            '$addToSet': {
                'likers': {'auth_user_id': user_id}
            }
        })
        try:
            content_col.update_one(post_filter, {
                    '$set': {
                        'likes': post['likes'] + 1
                    }
                })
        except KeyError:
            # If the post does not have the likes field, add it.
            content_col.update_one(post_filter, {
                    '$set': {
                        'likes': 1
                    }
                })

        if updated:
            user = auth_user_col.find_one({'auth_user_id': user_id})
            if user is not None:
                message = """
                {} {} liked your  post: {}.
                """.format(user["first_name"], user["last_name"], post['title'])
                to = post['author_id']
                send_notification_message(message, to)
            return jsonify({"ok": True,"message": "Successfully liked"})
        else:
            return jsonify({"ok": False,"message": "Something went wrong"})


@routes.route('/report-post/<post_id>', methods=['PATCH'])
@login_required()
def report_post(post_id):
    user_id = get_user_id()
    post_filter = {'_id': ObjectId(post_id)}

    reported = content_col.update_one(post_filter, {
        '$addToSet': {
            'reported_by': {'auth_user_id': user_id}
        }
    })

    if reported:
        return jsonify({"ok": True,"message": "Successfully reported"})
    else:
        return jsonify({"ok": False,"message": "Something went wrong"})


@routes.route('/unlike-post/<post_id>', methods=['PATCH'])
@login_required()
def unlike_post(post_id):
    user_id = get_user_id()
    post_filter = {'_id': ObjectId(post_id)}
    post = content_col.find_one(post_filter)
    Liked = content_col.find_one({'_id': ObjectId(post_id), "likers":{"auth_user_id": user_id}})
    if Liked is not None:
        removed_like = content_col.update_one(post_filter, {
            '$pull': {
                'likers': {'auth_user_id': user_id}
            }
        })
        try:
            content_col.update_one(post_filter, {
                    '$set': {
                        'likes': post['likes'] - 1
                    }
                })
        except KeyError:
            content_col.update_one(post_filter, {
                    '$set': {
                        'likes': 0
                    }
                })

        if removed_like:
            return jsonify({"ok": True,"message": "Successfully unliked"})
        else:
            return jsonify({"ok": False,"message": "Something went wrong"})
    else:
        return jsonify({"ok": False,"message": "Failed: Not liked"})


@routes.route('/post-comment/<post_id>', methods=['POST'])
@login_required()
def post_comment(post_id):
    user_id = get_user_id()
    if request.get_json():
        form_data = request.get_json()
        comment = form_data['comment']
    elif request.form:
        comment = request.form['comment']

    post_filter = {'_id': ObjectId(post_id)}

    if not comment:
        return jsonify({"ok": False,"message": "Comment not provided"})

    # Check if the comment is a duplicate
    if check_duplicate_comment(post_id, user_id, comment):
        return jsonify({"ok": False,"message": "Duplicate Comment"})

    posted_comment = content_col.update_one(post_filter, {
        '$addToSet': {
            'comments': {
                'user_id': user_id,
                'comment': comment,
                'posted_at': now.strftime("%Y-%m-%d %H:%M:%S")
            }
        }
    })

    if posted_comment:
        return jsonify({"ok": True,"message": "Comment successfully posted"})
    else:
        return jsonify({"ok": False,"message": "Something went wrong"})


@routes.route('/report-comment/<post_id>/<commenter_id>/<comment>', methods=['PATCH'])
@login_required()
def report_comment(post_id, commenter_id, comment):
    user_id = get_user_id()
    comment = urllib.parse.unquote_plus(comment)
    comment_filter = {
        '_id': ObjectId(post_id),
        'comments.user_id': commenter_id,
        'comments.comment': comment
    }

    reported_comment = content_col.update_one(comment_filter, {
        '$push': {
            'comments.$.reported_by': {'user_id': user_id}
        }
    })

    if reported_comment:
        return jsonify({"ok": True,"message": "Comment successfully reported"})
    else:
        return jsonify({"ok": False,"message": "Something went wrong"})


@routes.route('/withdraw-comment/<post_id>/<commenter_id>/<comment>', methods=['PATCH'])
def withdraw_comment(post_id, commenter_id, comment):
    if request.get_json():
        form_data = request.get_json()
        withdraw_reason = form_data['comment']
    elif request.form:
        withdraw_reason = request.form['comment']
    comment = urllib.parse.unquote_plus(comment)
    comment_filter = {
        '_id': ObjectId(post_id),
        'comments.user_id': commenter_id,
        'comments.comment': comment
    }

    withdrawn_comment = content_col.update_one(comment_filter, {
        '$set': {
            'comments.$.status': "Withdrawn",
            'comments.$.withdrawn_reason': withdraw_reason,
            'comments.$.withdrawn_at': now.strftime("%Y-%m-%d %H:%M:%S")
        }
    })

    if withdrawn_comment:
        return jsonify({"ok": True,"message": "Comment successfully withdrawn"})
    else:
        return jsonify({"ok": False,"message": "Something went wrong"})


@routes.route('/reported-comments', methods=['GET'])
def get_reported_comments():
    page = int(request.args.get("page", 1))

    all_comments = content_col.find({
        "status": {"$ne": "Withdrawn"},
        "comments.reported_by": {"$exists": True}
    }).sort("posted_at").skip(per_page * (page - 1)).limit(per_page)
    comment_count = content_col.count_documents({"status": {"$ne": "Withdrawn"}})
    method = ".get_reported_comments"
    links = {
        "self": {"href": url_for(method, page=page, _external=True)},
        "last": {
            "href": url_for(
                method, page=(comment_count // per_page) + 1, _external=True
            )
        },
    }
    # Add a 'prev' link if it's not on the first page:
    if page > 1:
        links["prev"] = {
            "href": url_for(method, page=page - 1, _external=True)
        }
    # Add a 'next' link if it's not on the last page:
    if page - 1 < comment_count // per_page:
        links["next"] = {
            "href": url_for(method, page=page + 1, _external=True)
        }
    return jsonify({
        "ok": True,
        "comments": [json.loads(json_util.dumps(content["comments"])) for content in all_comments],
        "_links": links
    })


@routes.route('/withdrawn-comments', methods=['GET'])
def get_withdrawn_comments():
    page = int(request.args.get("page", 1))

    all_comments = content_col.find({
        "comments.status": "Withdrawn"
    }).sort("posted_at").skip(per_page * (page - 1)).limit(per_page)
    comment_count = content_col.count_documents({"status": {"$ne": "Withdrawn"}})
    method = ".get_withdrawn_comments"
    links = {
        "self": {"href": url_for(method, page=page, _external=True)},
        "last": {
            "href": url_for(
                method, page=(comment_count // per_page) + 1, _external=True
            )
        },
    }
    # Add a 'prev' link if it's not on the first page:
    if page > 1:
        links["prev"] = {
            "href": url_for(method, page=page - 1, _external=True)
        }
    # Add a 'next' link if it's not on the last page:
    if page - 1 < comment_count // per_page:
        links["next"] = {
            "href": url_for(method, page=page + 1, _external=True)
        }
    return jsonify({
        "ok": True,
        "comments": [json.loads(json_util.dumps(content["comments"])) for content in all_comments],
        "_links": links
    })

# MICROSERVICE EVENTS
@routes.route('/event.user.signup', methods=['POST'])
@login_required()
def event_user_signup():
    if request.get_json():
        form_data = request.get_json()
        auth_user_id = form_data['auth_user_id']
        user_role = form_data['user_role']
        user_email = form_data['user_email']
        first_name = form_data['first_name']
        last_name = form_data['last_name']
    else:
        return jsonify({
            "ok": False,
            "message": "Empty request"
        })
    if check_duplicate_user(auth_user_id):
        return jsonify({"ok": False, "message": "User already exists"})
    user_created = auth_user_col.insert_one({
        'auth_user_id': auth_user_id,
        'user_role': user_role,
        'user_email': user_email,
        'first_name': first_name,
        'last_name': last_name
    }).inserted_id
    if user_created:
        return jsonify({"ok": True, "message": "Successfully inserted", "auth_user_id": str(user_created)})
    else:
        return jsonify({"ok": False, "message": "Something went wrong"})

@routes.route('/event.assign.role', methods=['POST'])
@admin_required()
def event_assign_role():
    if request.get_json():
        form_data = request.get_json()
        auth_user_id = form_data['auth_user_id']
        user_role = form_data['user_role']
    else:
        return jsonify({
            "ok": False,
            "message": "Empty request"
        })
    auth_user_filter = {'auth_user_id': auth_user_id}
    auth_user = auth_user_col.find_one(auth_user_filter)
    if auth_user:
        updated_user = auth_user_col.update_one(auth_user_filter, {
            '$set': {
                'user_role': user_role,
            }
            
        }).modified_count
    else:
        return jsonify({"ok": False, "message": "User does not exist"})
    if updated_user:
        return jsonify({"ok": True, "message": "Successfully updated role", "role": str(updated_user)})
    else:
        return jsonify({"ok": False, "message": "Something went wrong"})

@routes.route('/event.approve.post', methods=['POST'])
@admin_required()
def event_approve_post():
    if request.get_json():
        form_data = request.get_json()
        draft_id = form_data['content_post_id']
    else:
        return jsonify({"ok": False, "message": "Invalid request"})
    draft_filter = {'_id': ObjectId(draft_id)}
    draft = drafts_col.find_one(draft_filter)
    if draft:
        try:
            author_id = draft["author_id"]
            title = draft["title"]
            body = draft["body"]
            metadata = draft["metadata"]
            tags = draft["tags"]
            categories = draft["categories"]
            reviewers = draft["reviewers"]
        except KeyError:
            return jsonify({"ok": False,"message": "This draft has not submitted"})
    else:
        return jsonify({"ok": False,"message": "This draft doesn't exist"})

    # Check if any essential field is empty
    if not title or not body:
        return jsonify({"ok": False,"message": "Please provide all fields"})

    # Check if the article is a duplicate
    is_duplicate = check_duplicate_post(title, author_id)
    if is_duplicate and draft['update']:
        content_col.update_one({'title': title, 'body': body}, {
            '$set': {
                'status': '',
                'withdrawn_at': '',
                'withdrawn_reason': ''

            }
        })
        drafts_col.delete_one(draft_filter)
        return jsonify({"ok": True, "message": "Update approved"})
    elif is_duplicate:
        return jsonify({"ok": False, "message": "Duplicate Post"})
    else:
        author_filter = {'auth_user_id': author_id}
        author = auth_user_col.find_one(author_filter)

        inserted_id = content_col.insert_one({
            'author_id': author_id,
            'first_name': author['first_name'],
            'last_name': author['last_name'],
            'email': author['user_email'],
            'draft_id': draft_id,
            'title': title,
            'body': body,
            'read_time': read_time_in_minutes(body),
            'views': 0,
            'metadata': metadata,
            'tags': tags,
            'likes': 0,
            'categories': categories,
            'reviewers': reviewers,
            'likers': [],
            'slug': get_slug(title),
            'status': '',
            'isApproved': True,
            'published_at': now.strftime("%Y-%m-%d %H:%M")
        }).inserted_id
        drafts_col.delete_one({'_id': ObjectId(draft_id)})
        notification_data = {
                        "token": "QYmXTKt6bnzaFi76H7R88FQ",
                        "to": author['user_email'],
                        "filter": "post_approve",
                        "first_name": author['first_name'],
                        "title": title
                    }
        email_request = requests.post(NOTIFY_URL+'author', json=notification_data)
        if inserted_id:
            return jsonify({"ok": True,"message": "Successfully inserted", "inserted": str(inserted_id)})
        else:
            return jsonify({"ok": False,"message": "Something went wrong"})

@routes.route('/decline/<post_id>', methods=['POST'])
@admin_required()
def decline_post(post_id):
    form_data = request.get_json()
    reason = form_data['reason']

    post_filter = {'_id': ObjectId(post_id)}
    draft = drafts_col.find_one(post_filter)
    if draft:
        try:
            author_id = draft["author_id"]
            title = draft['title']
        except KeyError:
            return jsonify({"ok": False,"message": "This draft has not submitted"})
    else:
        return jsonify({"ok": False,"message": "This draft doesn't exist"})

    author_filter = {'auth_user_id': author_id}
    author = auth_user_col.find_one(author_filter)

    declined_post = drafts_col.update_one(post_filter, {
        '$set': {
            'status': 'Declined',
            'declined_at': now.strftime("%Y-%m-%d %H:%M")
        }
    }).modified_count
    notification_data = {
                    "token": "QYmXTKt6bnzaFi76H7R88FQ",
                    "to": author['user_email'],
                    "filter": "post_decline",
                    "first_name": author['first_name'],
                    "title": title,
                    "reason": reason
                }
    
    email_request = requests.post(NOTIFY_URL+'author', json=notification_data)

    if declined_post:
        return jsonify({"ok": True,"message": "Post declined", })
    else:
        return jsonify({"ok": False,"message": "Something went wrong"})

@routes.route('/withdraw-post/<post_id>', methods=['PATCH'])
@author_required()
def withdraw_post(post_id):
    author_id = get_user_id()
    if request.get_json():
        form_data = request.get_json()
        comment = form_data['comment']
        option = form_data['filter']
    elif request.form:
        comment = request.form['comment']
    
    if option == 'author':
        author_id = get_user_id()
        post_filter = {'_id': ObjectId(post_id), 'author_id': author_id}
    elif option == 'admin':
        post_filter = {'_id': ObjectId(post_id)}
    else:
        return jsonify({"ok": False,"message": "Something went wrong"})

    withdrawn_post = content_col.update_one(post_filter, {
        '$set': {
            'status': 'Withdrawn',
            'withdrawn_reason': comment,
            'withdrawn_at': now.strftime("%Y-%m-%d %H:%M:%S")
        }
    }).modified_count

    if withdrawn_post > 0:
        return jsonify({"ok": True,"message": "Successfully withdrawn", "updated": str(withdrawn_post)})
    else:
        return jsonify({"ok": False,"message": "Something went wrong"})

@routes.route('/stats', methods=['GET'])
@admin_required()
def get_stats():
    all_posts = content_col.find()
    number_all_posts = all_posts.count()
    number_approved_posts = content_col.find({'status': ''}).count()
    number_pending_posts = drafts_col.find({'status': 'Submitted'}).count()
    number_declined_posts = content_col.find({'status': 'Declined'}).count()
    number_withdrawn_posts = content_col.find({'status': 'Withdrawn'}).count()

    return jsonify({
        "ok": True,
        "stats": {
            "all": number_all_posts,
            "a": number_approved_posts,
            "p": number_pending_posts,
            "d": number_declined_posts,
            "w": number_withdrawn_posts
        }
    })

@routes.route('/stats/<author_id>', methods=['GET'])
@admin_required()
def get_author_stats(author_id):
    all_posts = content_col.find({'author_id': author_id})
    number_all_posts = all_posts.count()
    number_approved_posts = content_col.find({'author_id': author_id, 'status': ''}).count()
    number_pending_posts = drafts_col.find({'author_id': author_id, 'status': 'Submitted'}).count()
    number_declined_posts = content_col.find({'author_id': author_id, 'status': 'Declined'}).count()
    number_withdrawn_posts = content_col.find({'author_id': author_id, 'status': 'Withdrawn'}).count()

    return jsonify({
        "ok": True,
        "stats": {
            "all": number_all_posts,
            "a": number_approved_posts,
            "p": number_pending_posts,
            "d": number_declined_posts,
            "w": number_withdrawn_posts
        }
    })

@routes.route('/all-posts', methods=['GET'])
@admin_required()
def get_all():
    page = int(request.args.get("page", 1))
    option = request.args.get("filter", None)
    query = request.args.get("query", None)
    sort = request.args.get("sort", None)

    if option is not None and query is not None and sort is not None:
        search_filter = { option: query }
        all_content = content_col.find(search_filter).sort(sort).skip(per_page * (page - 1)).limit(per_page)
        content_count = content_col.count_documents(search_filter)
    elif sort is not None and option is None and query is None:
        all_content = content_col.find().sort(sort).skip(per_page * (page - 1)).limit(per_page)
        content_count = content_col.count_documents()
    else:
        all_content = content_col.find().skip(per_page * (page - 1)).limit(per_page)
        content_count = content_col.count_documents()


    if content_count > 0:
        return paginate(all_content, content_count, ".get_all", page, sort, option, query)
    else:
        return jsonify({"ok": False,"message": "No posts withdrawn"})

@routes.route('/all-posts/<slug>', methods=['GET'])
@admin_required()
def get_one_post_admin(slug):
    post = content_col.find_one({"slug": slug})
    if post:
        return jsonify({"ok": True, "message": json.loads(json_util.dumps(post))})
    else:
        return jsonify({"ok": False,"message": "Post doesn't exist"})
