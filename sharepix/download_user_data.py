from sharepix import celery, base_dir
from sharepix.models import User, ImagePost
from flask import url_for, json
import time

@celery.task
def downloads_task(username):
    user = User.query.filter_by(username=username).first_or_404()
    posts = ImagePost.query.filter_by(author = user)
    data = {}
    data[username] = []
    url = base_dir + '/static/'+username+'.txt'
    with open(url, 'w') as file_data:
        for post in posts:
            data_post = {
                'title':post.title,
                'image_content':post.image_content,
                'id':post.id,
                'created_at':post.date_posted
            }
            data[username].append(data_post)
            json.dump(data, file_data)
    return data
