#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Apr 10 13:35:38 2023

@author: liuzihan
"""
from flask import Flask, request, jsonify, render_template,redirect
from flask_socketio import SocketIO, emit
from pymongo import MongoClient, ASCENDING
#from bson import ObjectId
#import json
#import requests
#import websockets
import random
import string



app = Flask(__name__,static_url_path='/static')
socketio = SocketIO(app,cors_allowed_origins="*")
client = MongoClient('34.232.66.209', 27017, serverSelectionTimeoutMS=10000)
db = client.dsci551_project



'''
Functions for command URL on posts:
    GET:
        get_posts(): get multiple posts
        get_post_by_id(post_id): get one post
        get_post_field(post_id): get one attribute of one post
    POST:
        create_post(): create a new post (the _id will be generated)
    PUT:
        update_or_create_post(post_id): update the whole post (rewrite) if post_id exists else create a new post
    PATCH:
        update(post_id): update part of one specific post or whole post
    DELETE:
        delete_post_by_id(post_id): delete one specific post

Helper functions:
    convert_to_int_or_str(s): convert a string to integer if the string can be converted else remain as string
    generate_unique_id(length): generate an id containing A-Z, a-z, 0-9, -, _ with given length
    generate_post_id(): generate a new post id (11 characters) which is different from _id already exist in database 
'''
def convert_to_int_or_str(s):
    try:
        return int(s)
    except ValueError:
        return s


@app.route('/posts.json', methods=['GET'])
def get_posts():
    query_params = request.args.to_dict()
    
    if not query_params:
        # Return all posts without any sorting
        posts = db.posts.find()
    else:
        # Order posts according to query parameters
        order_by = request.args.get('orderBy','_id')

        if order_by == "$key":
            order_by = "_id"
        else:
            index = db.posts.index_information().keys()
            if not any([order_by in i for i in index]):
                create_index = input(f"Index on attribute {order_by} does not exist. Would you like to create an index? (y/n) ")
                if create_index.lower() == 'y':
                    db.posts.create_index([(order_by, ASCENDING)])
                    print(f"New index on {order_by} attribute is created")
                else:
                    return jsonify({'message': f"Index on attribute {order_by} does not exist."}), 400
        
        # Build the query based on the provided parameters
        query = {}
        if 'startAt' in query_params:
            if 'endAt' in query_params:
                query["$and"] = [{order_by:{'$gte': convert_to_int_or_str(query_params['startAt'])}}, 
                                 {order_by: {'$lte': convert_to_int_or_str(query_params['endAt'])}}]
            else:
                query[order_by] = {'$gte': convert_to_int_or_str(query_params['startAt'])}
        elif 'endAt' in query_params:
            query[order_by] = {'$lte': convert_to_int_or_str(query_params['endAt'])}
        elif 'equalTo' in query_params:
            query[order_by] = convert_to_int_or_str(query_params['equalTo'])
        
        total_posts = db.posts.count_documents(query)
        limit_to_first = int(request.args.get('limitToFirst', total_posts))
        limit_to_last = int(request.args.get('limitToLast', 0))
        
        if 'limitToLast' in query_params:
            skip = max(total_posts - limit_to_last, 0)
            posts = db.posts.find(query).sort(order_by).skip(skip).limit(limit_to_last)
        elif 'limitToFirst' in query_params:
            posts = db.posts.find(query).sort(order_by).limit(limit_to_first)
        else:
            posts = db.posts.find(query).sort(order_by)

    
    posts_list = [post for post in posts] # convert Cursor to list of dictionaries
    
    return jsonify(posts_list)

@app.route('/posts/<string:post_id>.json', methods=['GET'])
def get_post_by_id(post_id):
    post = db.posts.find_one({'_id': post_id}, {'_id': 0})
    if post:
        return jsonify(post)
    else:
        return jsonify({'error': 'Post not found'})

@app.route('/posts/<post_id>/<field>.json', methods=['GET'])
def get_post_field(post_id, field): 
    post = db.posts.find_one({'_id': post_id})
    if post:
        return jsonify({field: post.get(field)})
    else:
        return jsonify({'error': 'Post not found'})


def generate_unique_id(length):
    chars = string.ascii_letters + string.digits + '-_'
    return random.choice(string.ascii_uppercase) + ''.join(random.choices(chars, k= length - 1))

def generate_post_id():
    unique_key = generate_unique_id(11)
    while db.posts.find_one({'_id': unique_key}):
        unique_key = generate_unique_id(11)
    return unique_key

    
@app.route('/posts.json', methods=['POST'])
def create_post():
    # Get the JSON data from the request
    new_post = request.get_json()
    
    # Generate new post_id
    post_id = generate_post_id()
    
    # Update the post in the MongoDB collection
    new_post['_id'] = post_id
    db.posts.insert_one(new_post)

    # Return a success response
    return jsonify({'message': 'Post created successfully', '_id':post_id})


@app.route('/posts/<string:post_id>.json', methods=['PUT'])
def update_or_create_post(post_id):
    # Check if the post exists in the database
    post = db.posts.find_one({'_id': post_id})
    if post:
        # Update the existing post
        new_post = request.get_json()
        db.posts.update_one({'_id': post_id}, {'$set': new_post})
        
        return jsonify({'message': 'Post updated successfully'})
    else:
        # Create a new post
        new_post = request.get_json()
        new_post['_id'] = post_id
        db.posts.insert_one(new_post)
    
        return jsonify({'message': 'Post created successfully', '_id':post_id})


@app.route('/posts/<string:post_id>.json', methods=['PATCH'])
def update_post(post_id):
    # Check if the post exists in the database
    post = db.posts.find_one({'_id': post_id})
    if post:
        # Update the existing post
        new_post = request.get_json()
        db.posts.update_one({'_id': post_id}, {'$set': new_post})
        
        return jsonify({'message': 'Post updated successfully'})
    else:
        return jsonify({'error': 'Post not found'})


@app.route('/posts/<string:post_id>.json', methods=['DELETE'])
def delete_post_by_id(post_id):
    # Check if the post exists in the database
    post = db.posts.find_one({'_id': post_id})
    comments = db.comments.find({'post_id':post_id})
    if post:
        db.posts.delete_one({'_id':post_id})
        if comments:
            db.comments.delete_many({'post_id':post_id})
        return jsonify({'message': 'Post deleted successfully'})
    else:
        return jsonify({'error': 'Post not found'})



'''
Functions for command URL on comments:
    GET:
        get_comments(): get multiple comments
        get_post_comments(post_id): get comments under a specific post
        get_comment_by_id(post_id, comment_id): get a specific comment
        get_comment_field(post_id, comment_id): get one attribute of a specific comment
    POST:
        create_comment(post_id): add one comment under a specific post (the _id will be generated)
    PUT:
        update_or_create_comment(post_id, comment_id): update a specific comment if comment_id already exists else create a new comment
    PATCH:
        update_comment(post_id, comment_id): update part of a specific comment or whole comment
    DELETE:
        delete_comment(post_id, comment_id): delete a specific comment
Helper functions:
    generate_comment_id(post_id): generate a unique comment id in the format of 'post_id' + '_C' + number
'''    
@app.route('/comments.json', methods=['GET'])
def get_comments():
    query_params = request.args.to_dict()
    
    if not query_params:
        # Return all comments without any sorting
        comments = db.comments.find()
    else:
        # Order comments according to query parameters
        order_by = request.args.get('orderBy', 'post_id')
        
        if order_by == "$key":
            order_by = "post_id"
        else:
            index = db.comments.index_information().keys()
            if not any([order_by in i for i in index]):
                create_index = input(f"Index on attribute {order_by} does not exist. Would you like to create an index? (y/n) ")
                if create_index.lower() == 'y':
                    db.comments.create_index([(order_by, ASCENDING)])
                    print(f"New index on {order_by} attribute is created")
                else:
                    return jsonify({'message': f"Index on attribute {order_by} does not exist."}), 400
                
        # Build the query based on the provided parameters
        query = {}
        if 'startAt' in query_params:
            if 'endAt' in query_params:
                query["$and"] = [{order_by:{'$gte': convert_to_int_or_str(query_params['startAt'])}}, 
                                 {order_by: {'$lte': convert_to_int_or_str(query_params['endAt'])}}]
            else:
                query[order_by] = {'$gte': convert_to_int_or_str(query_params['startAt'])}
        elif 'endAt' in query_params:
            query[order_by] = {'$lte': convert_to_int_or_str(query_params['endAt'])}
        elif 'equalTo' in query_params:
            query[order_by] = convert_to_int_or_str(query_params['equalTo'])
    
        total_comments = db.comments.count_documents(query)
        limit_to_first = int(request.args.get('limitToFirst', total_comments))
        limit_to_last = int(request.args.get('limitToLast', 0))
        
        if 'limitToLast' in query_params:
            skip = max(total_comments - limit_to_last, 0)
            comments = db.comments.find(query).sort(order_by).skip(skip).limit(limit_to_last)
        elif 'limitToFirst' in query_params:
            comments = db.comments.find(query).sort(order_by).limit(limit_to_first)
        else:
            comments = db.comments.find(query).sort(order_by)
    
    comments_list = [comment for comment in comments] # convert Cursor to list of dictionaries
    
    return jsonify(comments_list)


@app.route('/comments/<string:post_id>.json', methods=['GET'])
def get_post_comments(post_id):
    query_params = request.args.to_dict()
    
    # Order comments according to query parameters
    order_by = request.args.get('orderBy', '_id')
    if order_by == '$key':
        order_by = '_id'
    elif order_by == '$value':
        order_by = 'comments'
    else:
        index = db.comments.index_information().keys()
        if not any([order_by in i for i in index]):
                create_index = input(f"Index on attribute {order_by} does not exist. Would you like to create an index? (y/n) ")
                if create_index.lower() == 'y':
                    db.comments.create_index([(order_by, ASCENDING)])
                    print(f"New index on {order_by} attribute is created")
                else:
                    return jsonify({'message': f"Index on attribute {order_by} does not exist."}), 400
    
    post = db.posts.find_one({'_id':post_id})
    # Check if the post exists in the database
    if post:
        # Build the query based on the provided parameters
        query = {'post_id': post_id}
        if 'startAt' in query_params:
            if 'endAt' in query_params:
                query["$and"] = [{order_by:{'$gte': convert_to_int_or_str(query_params['startAt'])}}, 
                                 {order_by: {'$lte': convert_to_int_or_str(query_params['endAt'])}}]
            else:
                query[order_by] = {'$gte': convert_to_int_or_str(query_params['startAt'])}
        elif 'endAt' in query_params:
            query[order_by] = {'$lte': convert_to_int_or_str(query_params['endAt'])}
        elif 'equalTo' in query_params:
            query[order_by] = convert_to_int_or_str(query_params['equalTo'])
    
        total_comments = db.comments.count_documents(query)
        limit_to_first = int(request.args.get('limitToFirst', total_comments))
        limit_to_last = int(request.args.get('limitToLast', 0))
        
        if 'limitToLast' in query_params:
            skip = max(total_comments - limit_to_last, 0)
            comments = db.comments.find(query, {'_id':1,'comments':1}).sort(order_by).skip(skip).limit(limit_to_last)
        elif 'limitToFirst' in query_params:
            comments = db.comments.find(query, {'_id':1,'comments':1}).sort(order_by).limit(limit_to_first)
        else:
            comments = db.comments.find(query, {'_id':1,'comments':1}).sort(order_by)
        
        comments_list = [comment for comment in comments] # convert Cursor to list of dictionaries
    
        return jsonify(comments_list) 
    else:
        return jsonify({'error':'Post not found'})


@app.route('/comments/<string:post_id>/<string:comment_id>.json', methods=['GET'])
def get_comment_by_id(post_id, comment_id):
    comment = db.comments.find_one({'_id': comment_id}, {'_id': 1, 'comments': 1})
    if comment:
        return jsonify(comment)
    else:
        return jsonify({'error': 'Comment not found'})


@app.route('/comments/<string:post_id>/<string:comment_id>/<field>.json', methods=['GET'])
def get_comment_field(post_id, comment_id, field):
    comment = db.comments.find_one({'_id': comment_id})
    if comment:
        return jsonify({field: comment.get(field)})
    else:
        return jsonify({'error': 'Comment not found'})


def generate_comment_id(post_id):
    cursor = db.comments.find({'post_id': post_id})
    if cursor:
        comments = [comment for comment in cursor]
        comment_numbers=[]
        for comment in comments:
            comment_id_parts = comment['_id'].split('_')
            if comment_id_parts[-1].startswith('C'):
                comment_number_str = comment_id_parts[-1][1:]
                if comment_number_str:
                    try:
                        comment_number = int(comment_number_str)
                        comment_numbers.append(comment_number)
                    except ValueError:
                        pass
        if comment_numbers:
            new_count = max(comment_numbers) + 1
        else:
            new_count = 1
        return f"{post_id}_C{new_count}"


@app.route('/comments/<string:post_id>.json', methods=['POST'])
def create_comment(post_id):
    new_comment = request.get_json()
    # Check if the post exists in the database
    post = db.posts.find_one({'_id':post_id})
    if post:
        new_comment['post_id'] = post_id
        new_comment['_id'] = generate_comment_id(post_id)
        db.comments.insert_one(new_comment)
        return jsonify({'message': 'Comment created successfully', '_id':new_comment['_id']})
    else:
        return jsonify({'error': 'Post not found'})
 

@app.route('/comments/<string:post_id>/<string:comment_id>.json', methods=['PUT'])
def update_or_create_comment(post_id, comment_id):
    new_comment = request.get_json()
    #Check if the post exists in the database
    post = db.posts.find_one({'_id':post_id})
    comment = db.comments.find_one({'_id':comment_id})
    if post:
        if comment:
            db.comments.update_one({'_id': comment_id}, {'$set': new_comment})
            
            return jsonify({'message': 'Comment updated successfully'})
        else:
            new_comment['_id'] = comment_id
            new_comment['post_id'] = post_id
            db.comments.insert_one(new_comment)

            return jsonify({'message': 'Comment created successfully', '_id':comment_id})
    else:
        return jsonify({'error': 'Post not found'})

        
@app.route('/comments/<string:post_id>/<string:comment_id>.json', methods=['PATCH'])
def update_comment(post_id, comment_id):
    # Check if the comment exists in the database
    comment = db.comments.find_one({'_id': comment_id})
    if comment:
        # Update the existing comment
        new_comment = request.get_json()
        db.comments.update_one({'_id': comment_id}, {'$set': new_comment})
        
        return jsonify({'message': 'Comment updated successfully'})
    else:
        return jsonify({'error': 'Comment not found'})
    

@app.route('/comments/<string:post_id>/<string:comment_id>.json', methods=['DELETE'])
def delete_comment_by_id(post_id, comment_id):
    # Check if the comment exists in the database
    comment = db.comments.find_one({'_id':comment_id})
    if comment:
        db.comments.delete_one({'_id':comment_id})
        return jsonify({'message': 'Comment deleted successfully'})
    else:
        return jsonify({'error': 'Comment not found'})
 

@app.route('/', methods=['GET'])
def posts():
    username = request.args.get('username')

    if username:
        return redirect('http://localhost:8000/' + username)
    return render_template('search.html')


@app.route('/<account_name>')
def account_posts(account_name):
    return render_template('account.html', account_name=account_name)


@app.route('/posts/<post_id>')
def comment(post_id):
    return render_template('comment1.html', post_id=post_id)



'''
Functions for Account Home Page:
    handle_get_account_posts(data): get ten posts of the specific account (ascendingly ordered by like number)
    handle_submit_post(data): add a new post of one specific account
    handle_like_post(post_id): increase the like number of one specific account by 1
    handle_delete_post(post_id): delete one specific post
'''
@socketio.on('get_account_posts')
def handle_get_account_posts(data):
    # Retrieve posts from database
    cursor = db.posts.find({'account_name':data['account_name']}).sort('like_number').limit(10)
    posts_list = [post for post in cursor]
    # convert Cursor to list of dictionaries
    emit('posts', posts_list)


@socketio.on('submit_post')
def handle_submit_post(data):
    # Generate new post_id
    post_id = generate_post_id()
    
    # Insert the post in the MongoDB collection
    data['_id'] = post_id
    data['like_number'] = 0
    db.posts.insert_one(data)
    
    # Retrieve updated list of posts from the database
    posts = db.posts.find({'account_name':data['account_name']}).sort('like_number').limit(10)
    posts_list = [post for post in posts]

    # Broadcast the updated list of posts to all connected clients
    emit('posts', posts_list, broadcast=True)


@socketio.on('like_post')
def handle_like_post(post_id):
    # Check if the post exists in the database
    post = db.posts.find_one({'_id': post_id})
    if post:
        db.posts.update_one({'_id': post_id}, {'$inc': {'like_number': 1}})
        
        # Broadcast the updated list of posts to all connected clients
        cursor = db.posts.find({'account_name': post['account_name']}).sort('like_number').limit(10)
        posts_list = [post for post in cursor] # convert Cursor to list of dictionaries
        emit('posts', posts_list, broadcast=True)
    else:
        return jsonify({'error': 'Post not found'})


@socketio.on('delete_post')
def handle_delete_post(post_id):
    # Check if the post exists in the database
    post = db.posts.find_one({'_id': post_id})
    if post:
        db.posts.delete_one({'_id':post_id})
        
        # Broadcast the updated list of posts to all connected clients
        cursor = db.posts.find({'account_name': post['account_name']}).sort('like_number').limit(10)
        posts_list = [post for post in cursor] # convert Cursor to list of dictionaries
        emit('posts', posts_list, broadcast=True)
    else:
        return jsonify({'error': 'Post not found'})


'''
Functions for Post Detail Page:
    handle_get_single_post(post_id): get the single post for specific post_id
    handle_get_post_comments(data): get all the comments under one specific post
    handle_submit_comment(data): add a new comment under one specific post
    handle_delete_comment(data): delete a commen under one specific post
'''
@socketio.on('get_single_post')
def handle_get_single_post(post_id):
    post = db.posts.find_one({'_id':post_id})
    emit('post', post)


@socketio.on('get_post_comments')
def handle_get_post_comments(data):
    # Retrieve posts from database
    cursor = db.comments.find({'post_id':data['post_id']})
    comments_list = [comment for comment in cursor] # convert Cursor to list of dictionaries
    emit('comments', comments_list)


@socketio.on('submit_comment')
def handle_submit_comment(data):
    # Generate new post_id

    comment_id = generate_comment_id(data['post_id'])
    #comment_id=generate_post_id()
    # Insert the post in the MongoDB collection
    data['_id'] = comment_id

    db.comments.insert_one(data)

    # Retrieve updated list of posts from the database
    comments = db.comments.find({'post_id':data['post_id']})
    comments_list = [comment for comment in comments]

    # Broadcast the updated list of posts to all connected clients
    emit('comments', comments_list, broadcast=True)
    

@socketio.on('delete_comment')
def handle_delete_comment(comment_id):
    # Check if the post exists in the database
    comment = db.comments.find_one({'_id': comment_id})
    if comment:
        db.comments.delete_one({'_id':comment_id})
        
        # Broadcast the updated list of posts to all connected clients
        cursor = db.comments.find({'post_id': comment['post_id']})
        comments_list = [comment for comment in cursor] # convert Cursor to list of dictionaries
        emit('comments', comments_list, broadcast=True)
    else:
        return jsonify({'error': 'Comment not found'})



if __name__ == '__main__':
    socketio.run(app, debug=True,port=8000)
#    app.run(debug=True)