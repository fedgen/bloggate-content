import re, requests
import urllib.parse
from flask import request, jsonify, url_for
from bson import json_util, ObjectId
from flask_cors import cross_origin
from flask_jwt_extended import jwt_required, get_jwt_identity
import json
from routes import routes, now, drafts_col, per_page, content_col, auth_user_col, author_required, reviewer_required, admin_required
from routes.content.main import publish_post
from routes.general_methods import get_random_reviewers, get_review_parameters, get_user_id, get_user_role, parse_comment, send_notification_message


@routes.route('/get-drafts', methods=['GET'])
@author_required()
def get_drafts():
    # JWT identity should be user id
    author_id = get_user_id()
    
    page = int(request.args.get("page", 1))

    search_filter = {
        'author_id': author_id,
        "status": "Draft"
    }
    drafts = drafts_col.find(search_filter).sort("updated_at", -1).skip(per_page * (page - 1)).limit(per_page)
    content_count = drafts_col.count_documents(search_filter)
    """
    links = {
        "self": {"href": url_for(".get_drafts", author_id=author_id, status=status, page=page, _external=True)},
        "last": {
            "href": url_for(
                ".get_drafts", author_id=author_id, status=status, page=(content_count // per_page) + 1, _external=True
            )
        },
    }
    # Add a 'prev' link if it's not on the first page:
    if page > 1:
        links["prev"] = {
            "href": url_for(".get_drafts", author_id=author_id, status=status, page=page - 1, _external=True)
        }
    # Add a 'next' link if it's not on the last page:
    if page - 1 < content_count // per_page:
        links["next"] = {
            "href": url_for(".get_drafts", author_id=author_id, status=status, page=page + 1, _external=True)
        }"""
    return jsonify({
        "ok": True,
        "posts": [json.loads(json_util.dumps(draft)) for draft in drafts]
    })


@routes.route('/create-draft', methods=['POST'])
#@cross_origin(supports_credentials=True)
@author_required()
def create_draft():
    user_id = get_user_id()
    author_filter = {'auth_user_id': user_id}
    author = auth_user_col.find_one(author_filter)
    # Apparently flask receives form input that comes in a json quite literally so the if/elif block accounts for
    # that and for normal input
    if request.get_json():
        form_data = request.get_json()
        title = form_data['title']
        body = form_data['body']
        filter= form_data['filter']
        if form_data['tags']:
            tags = form_data['tags']
        else:
            tags = "PHIS"
        if form_data['categories']:
            categories = form_data['categories']
        else:
            categories = "Uncategorized"
        if form_data['update']:
            update = form_data['update']
        else:
            update = False
    elif request.form:
        title = request.form['title']
        body = request.form['body']
        if request.form['tags']:
            tags = request.form['tags']
        else:
            tags = "PHIS"
        if request.form['categories']:
            categories = request.form['categories']
        else:
            categories = "Uncategorized"

    
    if (filter == "now"):
        reviewers = get_random_reviewers()
        inserted_id = drafts_col.insert_one({
            'author_id': user_id,
            'author_email': author['user_email'],
            'first_name': author['first_name'],
            'last_name': author['last_name'],
            'title': title,
            'body': body,
            'metadata': [],
            'tags': [s.capitalize() for s in set(tags)],
            'categories': [s.capitalize() for s in set(categories)],
            'status': 'Submitted',
            'created_at': now.strftime("%Y-%m-%d %H:%M:%S"),
            'reviewers': reviewers,
            'review_comments': [],
            'update': update
        }).inserted_id
    else:
        inserted_id = drafts_col.insert_one({
            'author_id': user_id,
            'author_email': author['user_email'],
            'first_name': author['first_name'],
            'last_name': author['last_name'],
            'title': title,
            'body': body,
            'metadata': [],
            'tags': [s.capitalize() for s in set(tags)],
            'categories': [s.capitalize() for s in set(categories)],
            'status': 'Draft',
            'created_at': now.strftime("%Y-%m-%d %H:%M:%S")
        }).inserted_id
 
    if inserted_id:
        return jsonify({"ok": True, "message": "Successfully inserted", "draft_id": str(inserted_id)})
    else:
        return jsonify({"ok": False, "message": "Something went wrong"})


@routes.route('/update-draft/<draft_id>', methods=['PUT'])
@author_required()
def update_draft(draft_id):
    author_id = get_user_id()
    draft_filter = {'_id': ObjectId(draft_id), 'author_id': author_id}
 
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

    

    updated_draft = drafts_col.update_one(draft_filter, {
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

    if updated_draft > 0:
        return jsonify({"ok": True, "message": "Successfully updated", "updated": str(updated_draft)})
    else:
        return jsonify({"ok": False, "message": "Something went wrong"})


@routes.route('/read-draft/<draft_id>', methods=['GET'])
@author_required()
def read_draft(draft_id):
    draft = drafts_col.find_one({"_id": ObjectId(draft_id)})
    return jsonify({"ok": True, "posts": json.loads(json_util.dumps(draft))})

@routes.route('/add-reviewer-comment', methods=['PATCH'])
@reviewer_required()
def add_comment():
    """Add a comment to draft"""
    user_id = get_user_id()
    user_role = get_user_role()
    if request.get_json():
        form_data = request.get_json()

    if user_role == "S":
        draft_filter = {'_id': ObjectId(form_data['draft_id']), "status": "Submitted"}
    elif user_role == "R":
        draft_filter = {'_id': ObjectId(form_data['draft_id']), "status": "Submitted", 'reviewers': user_id} 

    draft = drafts_col.find_one(draft_filter)
    comment = parse_comment(form_data, user_id)

    if draft is None:
        return jsonify({"ok": False, "message": "Unauthorized"}), 403
    
    if draft.get('review_comments'):
        drafts_col.update_one(draft_filter, {"$push": {"review_comments": comment}})

        message = """
        You have a new comment on your submitted post: {}. comment: {} recommendation: {}
        """.format(draft['title'], comment["comment"], comment["recommendation"])
        to = draft['author_id']
        send_notification_message(message, to)

        return jsonify({"ok": True, "object": "Comment", "message": "Comment added"}), 200
    else:
        # Create empty array of comments
        drafts_col.update_one(draft_filter, {"$set": {"review_comments": []}}) 
        
        # Push new comment
        drafts_col.update_one(draft_filter, {"$push": {"review_comments": comment}})
        
        # TODO: Notify Reviewer via Email
        message = """
        You have a new comment on your submitted post: {}. comment: {} recommendation: {}
        """.format(draft['title'], comment["comment"], comment["recommendation"])
        to = draft['author_id']
        send_notification_message(message, to)

        return jsonify({"ok": True, "object": "Comment", "message": "Comment created"}), 200
    
@routes.route('/edit-reviewer-comment/<comment_id>', methods=['PATCH'])
@reviewer_required()
def edit_comment(comment_id):
    """Edit a comment, only a comment author can edit comment"""
    user_id = get_user_id()
    user_role = get_user_role()
    if request.get_json():
        form_data = request.get_json()

    if user_role == "S":
        draft_filter = {
            '_id': ObjectId(form_data['draft_id']),
            'review_comments.name_id': user_id, 
            "status": "Submitted"}
    
    elif user_role == "R":
        draft_filter = {
            '_id': ObjectId(form_data['draft_id']), 
            "status": "Submitted", 
            'review_comments.name_id': user_id, 
            'reviewers': user_id} 

    draft = drafts_col.find_one(draft_filter)

    if draft is not None:
        drafts_col.update_one(
            {'_id': ObjectId(form_data['draft_id']), 'review_comments.name_id': user_id},
            {'$set': {
                'review_comments.$[xxx].comment': form_data['comment'],
                'review_comments.$[xxx].recommendation': form_data['recommendation']
            }},
            array_filters=[{"xxx.id": comment_id}]
        )
        message = """
        You have a new comment on your submitted post: {}. comment: {} recommendation: {}
        """.format(draft['title'], form_data["comment"], form_data["recommendation"])
        to = draft['author_id']
        send_notification_message(message, to)

        return jsonify({"ok": True, "message": "Comment updated"}), 200
    else:
        return jsonify({"ok": False, "message": "Comment not found"}), 404


@routes.route('/assign-reviewer', methods=['PATCH'])
@admin_required()
def assign_reviewer():
    """Add a reviwer to draft"""
    duplicates = []
    if request.get_json():
        form_data = request.get_json()
    reviewers = form_data['reviewers']
    if len(reviewers) > 0:
        for reviewer in form_data['reviewers']:
            draft_filter = {'_id': ObjectId(form_data['draft_id']), "status": "Submitted", 'reviewers': reviewer}
            
            draft = drafts_col.find_one(draft_filter)
            
            if draft is None:
                drafts_col.update_one({'_id': ObjectId(form_data['draft_id'])}, {"$push": {"reviewers": reviewer}})
                
                draft = drafts_col.find_one({'_id': ObjectId(form_data['draft_id'])})
                # TODO: Notify Reviewer via Email
                message = "You have been invited to review a post. Title: {}".format(draft['title'])
                url = "https://fedgen.net/dash/review/read/{}".format(form_data['draft_id'])
                to = reviewer
                send_notification_message(message, to, url)
            else:
                duplicates.append(reviewer)
                
        return jsonify({"ok": True, "message": "Reviewers added", "error": duplicates}), 201
    else:
        return jsonify({"ok": False, "message": "List cannot be empty", "error": "BadRequest"}), 400
    
@routes.route('/remove-reviewer', methods=['PATCH'])
@admin_required()
def remove_reviewer():
    """remove a reviwer to draft"""

    if request.get_json():
        form_data = request.get_json()
    draft_filter = {'_id': ObjectId(form_data['draft_id']), "status": "Submitted", 'reviewers': form_data['reviewer_id']}
    
    draft = drafts_col.find_one(draft_filter)
    
    if draft is not None:
        reviewers: list = draft['reviewers']
        reviewers.remove(form_data['reviewer_id'])
        drafts_col.update_one({'_id': ObjectId(form_data['draft_id'])}, {"$set": {"reviewers": reviewers}})
       
        # TODO: Notify Reviewer via Email
        message = "You have been removed as a reviewer from a post. Title: {}".format(draft['title'])
        to = form_data['reviewer_id']
        send_notification_message(message, to)
        
        return jsonify({"ok": True, "message": "Reviewer {} removed".format(form_data['reviewer_id'])}), 200
    else:
        return jsonify({"ok": False, "message": "Reviewer not Found"}), 404



@routes.route('/submit-draft/<draft_id>', methods=['POST'])
@author_required()
def submit_draft(draft_id):
    """Make sure draft is updated before it can be submitted"""
    draft_filter = {'_id': ObjectId(draft_id)}
    reviewers = get_random_reviewers()
    if request.get_json():
        form_data = request.get_json()
    updated_draft = drafts_col.update_one(draft_filter, {
        '$set': {
            'title': form_data['title'],
            'body': form_data['body'],
            'tags': [tag for tag in set(form_data['tags'])],
            'categories': [category for category in set(form_data['categories'])],
            'reviewers': reviewers,
            'review_comments': [],
            'status': 'Submitted'
        }
    }).modified_count

    draft = drafts_col.find_one(draft_filter)
    event_data = {
        'content_post_id': draft_id,
        'post_title': draft['title'],
        'post_content': draft['body']
    }
    #res = request.post('', event_data)
    return jsonify({"ok": True, "message": "Successfully submitted for approval", "updated": str(updated_draft)})
    # TODO: Add a producer to notify reviewers


@routes.route('/bin-draft/<draft_id>', methods=['PATCH'])
@author_required()
def bin_draft(draft_id):
    # Only drafts that haven't been published can be binned
    
    draft_filter = {
        '_id': ObjectId(draft_id),
        'status': {"$ne": "Published"}
    }

    updated_draft = drafts_col.update_one(draft_filter, {
        '$set': {
            'status': 'Binned'
        }
    }).modified_count

    if updated_draft > 0:
        return jsonify({"ok": True, "message": "Successfully binned", "updated": str(updated_draft)})
    else:
        return jsonify({"ok": False, "message": "Something went wrong"})


@routes.route('/review-draft/<draft_id>', methods=['PATCH'])
@reviewer_required()
def review_draft(draft_id):
    user_id = get_user_id()
    draft_filter = {
        '_id': ObjectId(draft_id),
        'reviewers.id': user_id
    }
    push_dict = {}
    total = 0
    review_parameters = get_review_parameters()["parameters"]
    if request.get_json():
        form_data = request.get_json()
        for i in review_parameters:
            if not form_data[i].isnumeric():
                return jsonify({"message": i + " value is not numeric"})
            push_dict["reviewers.$." + i] = int(form_data[i])
            total = total + int(form_data[i])
        push_dict["reviewers.$.comments"] = form_data["comments"]
    elif request.form:
        for i in review_parameters:
            if not request.form[i].isnumeric():
                return jsonify({"message": i + " value is not numeric"})
            push_dict["reviewers.$." + i] = int(request.form[i])
            total = total + int(request.form[i])
        push_dict["reviewers.$.comments"] = request.form["comments"]
    push_dict["reviewers.$.average"] = total / len(review_parameters)
    push_dict["reviewers.$.time_reviewed"] = now.strftime("%Y-%m-%d %H:%M:%S")

    reviewed_draft = drafts_col.update_one(draft_filter, {
        '$set': push_dict
    }).modified_count

    if reviewed_draft > 0:
        draft = drafts_col.find_one(draft_filter)
        reviewers_data = json.loads(json_util.dumps(draft))["reviewers"]
        total_average = 0

        for i in reviewers_data:
            # Check if all reviewers have reviewed
            if not "average" in i:
                return jsonify({"ok": True, "message": "Review successful. Other reviewer(s) still need to take a look"})
            total_average = total_average + i["average"]

        # If everyone has reviewed, check the score against the acceptable average score and do the needful
        # TODO: Add a producer to notify author of outcome
        average = total_average / len(reviewers_data)
        acceptable_average = get_review_parameters()["average score"]
        if average >= acceptable_average:
            publish_post(draft_id)
            drafts_col.update_one(draft_filter, {
                '$set': {'status': 'Published'}
            })
            return jsonify({"ok": True, "message": "Review complete. Post published"})
        else:
            drafts_col.update_one(draft_filter, {
                '$set': {'status': 'Unapproved'}
            })
            return jsonify({"ok": False, "message": "Review complete. Post unapproved"})
    else:
        return jsonify({"ok": False, "message": "Something went wrong"})


@routes.route('/get-drafts-for-reviewer/<draft_id>', methods=['GET'])
@reviewer_required()
def get_drafts_for_reviewer(draft_id):
    user_id = get_user_id()
    user_role = get_user_role()
    if user_role == "S":
        draft_filter = {'_id': ObjectId(draft_id), "status": "Submitted"}

    elif user_role == "R":
        draft_filter = {'_id': ObjectId(draft_id), 'status': 'Submitted', 'reviewers': user_id}
    else:
        return jsonify({"ok": True, "posts": [], "message": "No Posts"})
    

    submitted_drafts = drafts_col.find_one(draft_filter)

    if submitted_drafts:
        return jsonify({"ok": True, "posts": json.loads(json_util.dumps(submitted_drafts)), "ok": True})
    else:
        return jsonify({"ok": True, "posts": [], "message": "Not yet reviewed"})

@routes.route('/get-submitted-drafts', methods=['GET'])
#@cross_origin(supports_credentials=True)
@reviewer_required()
def get_submitted_drafts():
    user_id = get_user_id()
    user_role = get_user_role()
    if user_role == "S":
        draft_filter = {"status": "Submitted"}

    elif user_role == "R":
        draft_filter = {"status": "Submitted", 'reviewers': user_id} 
    

    submitted_drafts = drafts_col.find(draft_filter)

    if submitted_drafts:
        return jsonify({"ok": True, "posts":[json.loads(json_util.dumps(draft)) for draft in submitted_drafts], "ok": True})
    else:
        return jsonify({"ok": False, "posts": [], "message": "Not yet reviewed"})
    
@routes.route('/get-author-submitted-drafts', methods=['GET'])
@author_required()
def get_author_submitted_drafts():
    author_id = get_user_id()
    draft_filter = {"status": "Submitted", "author_id": author_id}

    submitted_drafts = drafts_col.find(draft_filter)

    if submitted_drafts:
        return jsonify({"ok": True, "posts":[json.loads(json_util.dumps(draft)) for draft in submitted_drafts], "ok": True})
    else:
        return jsonify({"ok": False, "posts": [], "message": "Not yet reviewed"})


@routes.route('/check-if-reviewer-has-reviewed/<draft_id>/<reviewer_id>', methods=['GET'])
def check_if_reviewer_has_reviewed(draft_id, reviewer_id):
    draft_filter = {
        '_id': ObjectId(draft_id),
        'reviewers.id': reviewer_id,
        'reviewers.time_reviewed': {'$exists': True}
    }

    reviewed_draft = drafts_col.find_one(draft_filter)

    if reviewed_draft:
        return jsonify({"message": "Reviewed"})
    else:
        return jsonify({"message": "Not yet reviewed"})


@routes.route('/check-draft-status/<draft_id>', methods=['GET'])
def check_draft_status(draft_id):
    """This method is to check the status of a draft that is submitted for approval"""
    published_draft_filter = {
        'draft_id': draft_id,
        'status': "Published",
    }
    withdrawn_draft_filter = {
        'draft_id': draft_id,
        'status': "Withdrawn",
    }

    published_draft = content_col.count_documents(published_draft_filter)
    withdrawn_draft = content_col.count_documents(withdrawn_draft_filter)

    if published_draft > 0:
        return jsonify({"message": "Published"})
    elif withdrawn_draft > 0:
        return jsonify({"message": "Published but withdrawn"})
    else:
        return jsonify({"message": "Not yet published"})


# Experimental
@routes.route('/autosave', methods=['POST'])
@author_required()
def autosave():
    user_id = get_user_id()
    author_filter = {'auth_user_id': user_id}
    author = auth_user_col.find_one(author_filter)
    # Apparently flask receives form input that comes in a json quite literally so the if/elif block accounts for
    # that and for normal input
    if request.get_json():
        form_data = request.get_json()
        if form_data['title']:
            title = form_data['title']
        else:
            title = "Untitled"
        if form_data['body']:
            body = form_data['body']
        else:
            body = ""

        if form_data['tags']:
            tags = form_data['tags']
        else:
            tags = []
        if form_data['categories']:
            categories = form_data['categories']
        else:
            categories = []
    if form_data['draft_id']:
        draft_filter = {
            '_id': ObjectId(form_data['draft_id'])
        }
    else:
        draft_filter = {
            'title': title
        }

    inserted_id = drafts_col.insert_one({
        'author_id': user_id,
        'author_email': author['user_email'],
        'first_name': author['first_name'],
        'last_name': author['last_name'],
        'title': title,
        'body': body,
        'metadata': [],
        'tags': [s.capitalize() for s in set(tags)],
        'categories': [s.capitalize() for s in set(categories)],
        'status': 'Submitted',
        'created_at': now.strftime("%Y-%m-%d %H:%M:%S"),
        'reviewers': [],
        'review-comment': []
    }).inserted_id
    
 
    if inserted_id:
        return jsonify({"ok": True, "message": "Successfully inserted", "draft_id": str(inserted_id)})
    else:
        return jsonify({"ok": False, "message": "Something went wrong"})

