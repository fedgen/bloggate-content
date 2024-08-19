import math, datetime, secrets, requests
import json
import jwt

from flask import url_for, jsonify, request, make_response
from routes.seo.main import get_slug
from bson import json_util, ObjectId

from . import content_col, per_page, now, auth_user_col


secret = "QYmXTKt6bnzaFi76H7R88FQ"
BACKEND_URL = "https://phis.fedgen.net"
def get_user_id():
    token = request.headers.get('Authorization')
    if not token:
        return jsonify({"ok": False, "message": "Unathorized"}), 403
    else:
        try:
            payload = jwt.decode(token, secret, algorithms=['HS256'])
            
            if payload:
                return payload['id']
            else:
                return jsonify({"ok": False, "message": "Invalid token"}), 403
        except jwt.ExpiredSignatureError:
            return jsonify({"ok": False, "message": "Expired token"}), 403

def get_user_role():
    token = request.headers.get('Authorization')
    if not token:
        return jsonify({"ok": False, "message": "Unathorized"}), 403
    else:
        try:
            payload = jwt.decode(token, secret, algorithms=['HS256'])
            
            if payload:
                return payload['role']
            else:
                return jsonify({"ok": False, "message": "Invalid token"}), 403
        except jwt.ExpiredSignatureError:
            return jsonify({"ok": False, "message": "Expired token"}), 403

def check_duplicate_post(title, author_id):
    duplicate_post = content_col.find_one({"title": title, "status": ""})
    if duplicate_post is None:
        return False
    return True


def check_duplicate_comment(post_id, commenter_id, comment):
    duplicate_comment = content_col.find_one({
        "_id": ObjectId(post_id),
        "comments.user_id": commenter_id,
        "comments.comment": comment
    })
    return json.loads(json_util.dumps(duplicate_comment))
def check_duplicate_user(user_id):
    duplicate_user = auth_user_col.find_one({
        "auth_user_id": user_id
    })
    if duplicate_user is not None:
        return True
    else:
        return False

def get_number_of_reviewers():
    """This function will be a consumer for the number of reviewers we need to approve a post before it's published
    from the admin service"""
    return 2


def get_random_reviewers():
    """This function will be a consumer for the reviewers we need to approve the post based on the number gotten from
    the function above before it's published from the admin service"""
    reviewers = []
    
    return reviewers


def get_review_parameters():
    """This function will be a consumer for the review criteria we need to approve a post before it's published
        from the admin service"""
    return {
        "parameters": ["Grammar", "Accuracy"],
        "average score": 65
    }

def get_user_full_name(user_id):
    user = auth_user_col.find_one({"auth_user_id": user_id})
    return " ".join([user['first_name'], user['last_name']])

def parse_comment(data, user_id):
    id = "cmt_" + secrets.token_urlsafe(6).replace("-", "").replace("_", "")
    name = get_user_full_name(user_id)
    name_id = user_id
    parent = data.get("parent", "") # Future feature for replies
    children = []
    comment = data['comment']
    recommendation = data['recommendation']
    date = datetime.datetime.now()

    return {
        "id": id,
        "name": name,
        "name_id": name_id,
        "parent": parent,
        "children": children,
        "comment": comment,
        "recommendation": recommendation,
        "date": date
    }




def paginate(all_content, count, method, page, sort=None, option=None, query=None):
    next_page = None
    previous_page = None

    if count % per_page != 0:
        last_page = (count // per_page) + 1
    elif count % per_page == 0:
        last_page = count / per_page

    links = {
        "self": {"href": url_for(
            method, page=page, filter=option, sort=sort, query=query, _external=True
            )
            },
        "last": {
            "href": url_for(
                method, page=last_page, filter=option, sort=sort, query=query, _external=True
            )
        },
    }

    # Add a 'prev' link if it's not on the first page:
    if page > 1:
        links["previous"] = {
            "href": url_for(method, page=page - 1, filter=option, sort=sort, query=query, _external=True)
        }
        previous_page = page - 1

    # Add a 'next' link if it's not on the last page:
    if page  < last_page:
        links["next"] = {
            "href": url_for(method, page=page + 1, filter=option, sort=sort, query=query, _external=True)
        }
        next_page = page + 1
    
    pages = {
                'next_page': next_page,
                'current_page': page,
                'previous_page': previous_page,
                'last_page': last_page
            }

    return jsonify({
        "ok": True,
        "links": links,
        "pages": pages,
        "count": count,
        "posts": [json.loads(json_util.dumps(content)) for content in all_content]
    })


def insert_cookie(slug, user_id):
    cookie = get_cookie()

    post_opened_filter = {
        'slug': slug,
        'opens.cookie': cookie
    }
    post_opened = content_col.count_documents(post_opened_filter)
    if post_opened == 0:
        post_filter = {'slug': slug}

        if user_id == 0:
            opens = {
                'cookie': cookie
            }
        else:
            opens = {
                'cookie': cookie,
                'user_id': user_id
            }
        content_col.update_one(post_filter, {
            '$addToSet': {
                'opens': opens
            }
        })


def get_cookie():
    if not request.cookies.get('time'):
        res = make_response("Setting a cookie")
        res.set_cookie('time', now.strftime("%Y-%m-%d"), max_age=60 * 60 * 24)
        return request.cookies.get('time')
    else:
        return request.cookies.get('time')


def read_time_in_minutes(body):
    body_length = len(body)
    words_per_minute = 310

    read_time = body_length / words_per_minute

    return math.ceil(read_time)

def pagination(queryset, page_size, page, url):
    count = queryset.count

def generate_token():
    payload = {
            'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=3),
            'iat': datetime.datetime.utcnow()
        }

    token = jwt.encode(payload, secret, algorithm='HS256')
    
    return token

def send_notification_message(message, to, url=None):
    """Sends in-app notification to user"""
    event_data = {
                "to": to,
                "message": message,
                "url": url
            }
    token = generate_token()
    header = {'Authorization': token}
    req = requests.post(BACKEND_URL + '/notify/messages', json=event_data, headers=header)

    if req.ok:
        return True
    else:
        return False