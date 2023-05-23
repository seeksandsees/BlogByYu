from flask import Flask, render_template, redirect, url_for, flash, abort
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor, CKEditorField
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from sqlalchemy.exc import NoResultFound
from sqlalchemy import ForeignKey
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from flask_gravatar import Gravatar
from functools import wraps
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_KEY')
ckeditor = CKEditor(app)
Bootstrap5(app)

##SET UP LOGIN MANAGER
login_manager = LoginManager()
login_manager.init_app(app)

##GRAVATAR for the commenter images
gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

##CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


##CONFIGURE TABLES

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String, nullable=False)
    password = db.Column(db.String, nullable=False)
    name = db.Column(db.String, nullable=False)
    posts = relationship('BlogPost', back_populates='author')  # this is important
    comments = relationship('Comment', back_populates='commenter')
    # back_populates is better than backref.
    # The latter creates a column in the other table automatically, so you only need one backref statement.
    # But it is better practice to do things explicitly.
    # So explicitly create columns in both linked tables, define relationship to the other class,
    # specify column with which this one corresponds. And see below for author_id as the joint.

class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)

# the author_id is supplied from the users table. NB hence the name users, since this is the tablename. And id is the column of course.
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # dit is de joint
# relationship is like this: ('Class name' with which to connect, and then the column in that db Model to communicate content
    author = relationship('User', back_populates='posts')  # this is important
    comments = relationship('Comment', back_populates='post')
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)

class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    commenter_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    commenter = relationship('User', back_populates='comments')
    post_id = db.Column(db.Integer, db.ForeignKey('blog_posts.id'))
    post = relationship('BlogPost', back_populates='comments')
    text = db.Column(db.String, nullable=False)

with app.app_context():
    db.create_all()


def admin_only(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            id = current_user.id
        except AttributeError:
            return redirect(url_for('get_all_posts'))
        else:
            if id != 1:
                return abort(403)
            else:
                return func(*args, **kwargs)
    return wrapper

@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts)


@app.route('/register', methods=['GET', 'POST'])
def register():
    register_form = RegisterForm()
    if register_form.validate_on_submit():
        check_user = db.session.execute(db.select(User).filter_by(email=register_form.email.data)).first()
        if not check_user:
            hashed_pw = generate_password_hash(register_form.password.data, method='pbkdf2:sha256', salt_length=8)
            user = User(
                email=register_form.email.data,
                password=hashed_pw,
                name=register_form.name.data
            )
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for('get_all_posts'))
        else:
            flash('We already have this address on file, please log in.')
            return redirect(url_for('login'))
    return render_template("register.html", form=register_form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    login_form = LoginForm()
    if login_form.validate_on_submit():
        try:
            user = db.session.execute(db.select(User).filter_by(email=login_form.email.data)).scalar_one()
        except NoResultFound:
            flash('Unknown user')
            return redirect(url_for('login'))
        else:
            if check_password_hash(user.password, login_form.password.data):
                login_user(user)
                return redirect(url_for('get_all_posts'))
            else:
                flash('Invalid password')
                return redirect(url_for('login'))
    return render_template("login.html", form=login_form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=['GET', 'POST'])
def show_post(post_id):
    requested_post = BlogPost.query.get(post_id)
    form = CommentForm()
    if form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("You need to log in or register in order to leave comments.")
            return redirect(url_for('login'))
        else:
            comment = Comment(
                text=form.comment.data,
                commenter=current_user,
                post=requested_post
            )
            db.session.add(comment)
            db.session.commit()
            return redirect(url_for('show_post', post_id=post_id))
    return render_template("post.html", post=requested_post, form=form)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/new-post", methods=['GET', 'POST'])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>", methods=['GET', 'POST'])
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000, debug=True)
