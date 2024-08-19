import urllib.parse

from flask import request, jsonify, url_for
from bson import json_util
from flask_jwt_extended import jwt_required, get_jwt_identity
import json
from routes import routes, preferences_col, content_col, db, per_page


@routes.route('/add-author-preference/<author_id>', methods=['PATCH'])
@jwt_required()
def add_author_preference(author_id):
    viewer_id = get_jwt_identity()
    if not author_id.isnumeric():
        return jsonify({"message": "Wrong author id"})

    user_filter = {
        'user_id': int(viewer_id)
    }

    added_author = preferences_col.update_one(user_filter, {
        '$push': {
            'authors': int(author_id)
        }
    }, upsert=True)

    if added_author > 0:
        return jsonify({"message": "Successfully updated", "updated": str(added_author)})
    else:
        return jsonify({"message": "Something went wrong"})


@routes.route('/remove-author-preference/<author_id>', methods=['PATCH'])
def remove_author_preference(author_id):
    viewer_id = get_jwt_identity()
    if not author_id.isnumeric():
        return jsonify({"message": "Wrong author id"})

    user_filter = {
        'user_id': int(viewer_id)
    }

    removed_author = preferences_col.update_one(user_filter, {
        '$pull': {
            'authors': int(author_id)
        }
    })

    if removed_author:
        return jsonify({"message": "Successfully updated", "updated": str(removed_author)})
    else:
        return jsonify({"message": "Something went wrong"})


@routes.route('/add-category-preference/<category>', methods=['PATCH'])
@jwt_required()
def add_category_preference(category):
    viewer_id = get_jwt_identity()
    category = urllib.parse.unquote_plus(category)
    user_filter = {
        'user_id': int(viewer_id)
    }

    added_category = preferences_col.update_one(user_filter, {
        '$push': {
            'categories': category.capitalize()
        }
    }, upsert=True)

    if added_category:
        return jsonify({"message": "Successfully updated", "updated": str(added_category)})
    else:
        return jsonify({"message": "Something went wrong"})


@routes.route('/remove-category-preference/<category>', methods=['PATCH'])
@jwt_required()
def remove_category_preference(category):
    viewer_id = get_jwt_identity()
    category = urllib.parse.unquote_plus(category)
    user_filter = {
        'user_id': int(viewer_id)
    }

    removed_category = preferences_col.update_one(user_filter, {
        '$pull': {
            'categories': category.capitalize()
        }
    })

    if removed_category:
        return jsonify({"message": "Successfully updated", "updated": str(removed_category)})
    else:
        return jsonify({"message": "Something went wrong"})


@routes.route('/add-tag-preference/<tag>', methods=['PATCH'])
@jwt_required()
def add_tag_preference(tag):
    viewer_id = get_jwt_identity()
    tag = urllib.parse.unquote_plus(tag)
    user_filter = {
        'user_id': int(viewer_id)
    }

    added_tag = preferences_col.update_one(user_filter, {
        '$push': {
            'tags': tag.capitalize()
        }
    }, upsert=True)

    if added_tag:
        return jsonify({"message": "Successfully updated", "updated": str(added_tag)})
    else:
        return jsonify({"message": "Something went wrong"})


@routes.route('/remove-tag-preference/<tag>', methods=['PATCH'])
@jwt_required()
def remove_tag_preference(tag):
    viewer_id = get_jwt_identity()
    tag = urllib.parse.unquote_plus(tag)
    user_filter = {
        'user_id': int(viewer_id)
    }

    removed_tag = preferences_col.update_one(user_filter, {
        '$pull': {
            'tags': tag.capitalize()
        }
    })

    if removed_tag:
        return jsonify({"message": "Successfully updated", "updated": str(removed_tag)})
    else:
        return jsonify({"message": "Something went wrong"})


@routes.route('/get-preferred-authors', methods=['GET'])
@jwt_required()
def get_preferred_authors():
    viewer_id = get_jwt_identity()
    user_filter = {
        'user_id': int(viewer_id)
    }

    user_preference = preferences_col.find_one(user_filter)
    return jsonify(user_preference["authors"])


@routes.route('/preferred-tags', methods=['GET'])
@jwt_required()
def get_preferred_tags():
    viewer_id = get_jwt_identity()
    user_filter = {
        'user_id': int(viewer_id)
    }

    user_preference = preferences_col.find_one(user_filter)
    return jsonify(user_preference["tags"])


@routes.route('/preferred-categories', methods=['GET'])
@jwt_required()
def get_preferred_categories():
    viewer_id = get_jwt_identity()
    user_filter = {
        'user_id': int(viewer_id)
    }

    user_preference = preferences_col.find_one(user_filter)
    return jsonify(user_preference["categories"])


@routes.route('/posts-with-author-preference', methods=['GET'])
@jwt_required()
def get_posts_with_author_preference():
    viewer_id = get_jwt_identity()
    page = int(request.args.get("page", 1))

    user_filter = {
        'user_id': int(viewer_id)
    }

    user_preference = preferences_col.find_one(user_filter)

    author_preference = {'author_id': {"$in": user_preference["authors"]}}
    all_content = db.content.find([author_preference]).sort("published_at").skip(per_page * (page - 1)).limit(per_page)
    content_count = content_col.count_documents(author_preference)
    links = {
        "self": {"href": url_for(".get_posts_with_author_preference", viewer_id=viewer_id, page=page, _external=True)},
        "last": {
            "href": url_for(
                ".get_posts_with_author_preference", viewer_id=viewer_id, page=(content_count // per_page) + 1, _external=True
            )
        },
    }
    # Add a 'prev' link if it's not on the first page:
    if page > 1:
        links["prev"] = {
            "href": url_for(".get_posts_with_author_preference", viewer_id=viewer_id, page=page - 1, _external=True)
        }
    # Add a 'next' link if it's not on the last page:
    if page - 1 < content_count // per_page:
        links["next"] = {
            "href": url_for(".get_posts_with_author_preference", viewer_id=viewer_id, page=page + 1, _external=True)
        }
    return jsonify({
        "posts": [json.loads(json_util.dumps(content)) for content in all_content],
        "_links": links
    })
