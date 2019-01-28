import os
import time
import secrets
from PIL import Image
from sharepix import celery
from werkzeug.utils import secure_filename
from sharepix.models import User, ImagePost
from sharepix import app, base_dir, db, bcrypt
from flask_login import login_user, current_user, logout_user, login_required
from sharepix.forms import RegistrationForm, LoginForm, UpdateAccountForm, PhotoForm
from flask_uploads import UploadSet, configure_uploads, IMAGES, patch_request_class
from flask import render_template, url_for, flash, redirect, send_from_directory, request, abort, send_file, json


UPLOAD_FOLDER = '/home/chigod/Pictures'
app.config['UPLOADED_PHOTOS_DEST'] = base_dir + '/static/images'
photos = UploadSet('photos', IMAGES)
configure_uploads(app, photos)
patch_request_class(app, size=64*250*250)


@app.route("/")
@app.route("/home")
def home():
    page = request.args.get('page', 1, type=int)
    posts = ImagePost.query.paginate(page=page, per_page=5)
    return render_template('home.html', posts=posts)


@app.route("/about")
def about():
    return render_template('about.html', title='About')


@app.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data, email=form.email.data, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash(f'Your account has been created!', 'success')
        return redirect(url_for('home'))
    return render_template('register.html', title='Register', form=form)


@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            flash('Login Unsuccessful. Please check username or password', 'danger')
    return render_template('login.html', title='Login', form=form)


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('home'))


def save_profile(form_picture):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    profile_fn = random_hex + f_ext
    profile_path = os.path.join(app.root_path, 'static/profile_pics', profile_fn)
    output_size = (125, 125)
    i = Image.open(form_picture)
    i.thumbnail(output_size)
    i.save(profile_path)

    return profile_fn

@app.route("/account", methods=['GET', 'POST'])
@login_required
def account():
    form = UpdateAccountForm()
    if form.validate_on_submit():
        if form.picture.data:
            profile_file = save_profile(form.picture.data)
            current_user.profile_img = profile_file
        current_user.username = form.username.data
        current_user.email = form.email.data
        db.session.commit()
        flash('Your account has been updated!', 'success')
        return redirect(url_for('account'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.email.data = current_user.email
    profile_img = url_for('static', filename='profile_pics/' + current_user.profile_img)
    return render_template('account.html', title='Account', profile_img=profile_img, form=form)


@app.route('/upload/new', methods=['GET', 'POST'])
@login_required
def upload_image():
    form = PhotoForm()
    if request.method == 'POST' and 'photo' in request.files:
        filename = photos.save(request.files['photo'])
        flash('Image has been successfully uploaded', 'success')
        post = ImagePost(title = form.title.data, image_content=filename, author=current_user)
        db.session.add(post)
        db.session.commit()
        return redirect(url_for('home'))
    return render_template('create_post.html', form=form)


@app.route('/images/<int:post_id>')
@login_required
def image(post_id):
    post = ImagePost.query.get_or_404(post_id)
    return render_template('show_images.html', title=post.title, post=post)

@app.route('/images/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    post = ImagePost.query.get_or_404(post_id)
    if post.author != current_user:
        abort(403)
    db.session.delete(post)
    db.session.commit()
    flash('Your post has been deleted!', 'success')
    return redirect(url_for('home'))


@app.route("/user/<string:username>")
def user_posts(username):
    page = request.args.get('page', 1, type=int)
    user = User.query.filter_by(username=username).first_or_404()
    posts = ImagePost.query.filter_by(author=user) \
            .order_by(ImagePost.date_posted.desc()) \
            .paginate(page=page, per_page=5)
    return render_template('user_posts.html', posts=posts, user=user)


@app.route('/user/download/<string:username>')
@login_required
def downloads(username):
    print(username)
    downloads_task.apply_async((username))
    return redirect('home')


@celery.task(bind=True)
def downloads_task(self, username):
    user = User.query.filter_by(username=username).first_or_404()
    posts = ImagePost.query.filter_by(author=user)
    data = {}
    data[username] = []
    url = base_dir + url_for('static', filename='download.txt')
    print(url)
    with open(url, 'w') as file_d:
        for post in posts:
            time.sleep(5)
            dpost = {}
            dpost['title'] = post.title
            dpost['image_content'] = post.image_content
            dpost['id'] = post.id
            dpost['date_posted'] = post.date_posted
            data[username].append(dpost)
            json.dump(dpost, file_d)
    return send_file(url, as_attachment=True)
