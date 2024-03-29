#Import Flask Library
from flask import Flask, render_template, request, session, url_for, redirect
import json
import hashlib
import os
import time
import pymysql.cursors

#Initialize the app from Flask
app = Flask(__name__)

# Initialize SALT for password
SALT = 'cs3083'

#Added a static folder to save images and serve them
IMAGES_DIR = os.path.join(os.getcwd(), "static")

#Configure MySQL
conn = pymysql.connect(host='localhost',
                       port = 3306,
                       user='irvin',
                       password='Itstuy14308!',
                       db='Finstagram',
                       charset='utf8mb4',
                       cursorclass=pymysql.cursors.DictCursor)

#Define a route to hello function
@app.route('/')
def hello():
    # return 'hello world'
    return render_template('index.html')

#Define route for login
@app.route('/login')
def login():
    return render_template('login.html')

#Define route for register
@app.route('/register')
def register():
    return render_template('register.html')

#Authenticates the login
@app.route('/loginAuth', methods=['GET', 'POST'])
def loginAuth():
    #grabs information from the forms
    username = request.form['username']
    password = request.form['password'] + SALT
    hashed_password = hashlib.sha256(password.encode('utf-8')).hexdigest()
    #cursor used to send queries
    cursor = conn.cursor()
    #executes query
    query = 'SELECT * FROM Person WHERE username = %s and password = %s'
    cursor.execute(query, (username, hashed_password))
    #stores the results in a variable
    data = cursor.fetchone()
    #use fetchall() if you are expecting more than 1 data row
    cursor.close()
    error = None
    if(data):
        #creates a session for the the user
        #session is a built in
        session['username'] = username
        return redirect(url_for('home'))
    else:
        #returns an error message to the html page
        error = 'Invalid login or username'
        return render_template('login.html', error=error)

# Authenticates the register
@app.route('/registerAuth', methods=['GET', 'POST'])
def registerAuth():
    #grabs information from the forms
    username = request.form['username']
    password = request.form['password'] + SALT
    first_name = request.form['first_name']
    last_name = request.form['last_name']
    bio = request.form['bio']
    hashed_password = hashlib.sha256(password.encode('utf-8')).hexdigest()
    # cursor used to send queries
    cursor = conn.cursor()
    # executes query
    query = 'SELECT * FROM Person WHERE username = %s'
    cursor.execute(query, (username))
    # stores the results in a variable
    data = cursor.fetchone()
    # use fetchall() if you are expecting more than 1 data row
    error = None
    if(data):
        # If the previous query returns data, then user exists
        error = "This user already exists"
        return render_template('register.html', error = error)
    else:
        ins = 'INSERT INTO Person VALUES(%s, %s, %s, %s, %s)'
        cursor.execute(ins, (username, hashed_password, first_name, last_name, bio))
        conn.commit()
        cursor.close()
        return render_template('index.html')

# Load home page
@app.route('/home')
def home():
    #load the user's post
    user = session['username']
    cursor = conn.cursor()
    query = 'SELECT postingdate, photoID, caption FROM Photo WHERE photoPoster = %s ORDER BY postingdate DESC'
    cursor.execute(query, (user))
    data = cursor.fetchall()
    cursor.close()
    return render_template('home.html', username=user, posts=data)

# Go to upload image page
@app.route('/upload_image')
def upload_image():
    username = session['username']
    cursor = conn.cursor()
    query = 'SELECT groupName, owner_username FROM BelongTo WHERE member_username = %s'
    cursor.execute(query, (username))
    data = cursor.fetchall()
    cursor.close()
    return render_template('upload.html', groups=data)

# Upload image
@app.route('/post', methods=['POST'])
def post():
    username = session['username']
    if request.files:
        # retrieve appropriate information for insertion 
        image_file = request.files.get("imageToUpload", "")
        allFollowers = True if request.form['allFollowers'] == 'True' else False
        caption = request.form['caption']
        image_name = image_file.filename
        friendGroups = request.form.getlist('shareGroup')
        filepath = os.path.join(IMAGES_DIR, image_name)
        image_file.save(filepath)
        # add photo to database 
        query = 'INSERT INTO Photo (postingdate, filepath, allFollowers, caption, photoPoster) VALUES (%s, %s, %s, %s, %s)'
        cursor = conn.cursor()
        cursor.execute(query, (
            time.strftime('%Y-%m-%d %H:%M:%S'), image_name, allFollowers, caption, username))
        conn.commit()
        # find id of photo that was just uploaded
        query = 'SELECT max(photoID) AS ID FROM Photo WHERE photoPoster = %s'
        cursor.execute(query, (username))
        data = cursor.fetchone()
        # share photo with selected friend groups 
        query = 'INSERT INTO SharedWith (groupOwner, groupName, photoID) VALUES (%s, %s, %s)'
        for friendGroup in friendGroups:
            friendGroup = json.loads(friendGroup)
            cursor.execute(query, (friendGroup['ownername'], friendGroup['groupname'], data['ID']))
        conn.commit()
        cursor.close()
        message = "Image has been successfully uploaded!"
        return render_template('message.html', page='upload_image', message=message)
    else:
        message = "Failed to upload image."
        return render_template('message.html', page='upload_image', message=message)

# Go to tag user page
@app.route('/tag_user/<prev_page>/<photo_id>')
def tag_user(prev_page, photo_id):
    return render_template('tag_user.html', prev_page=prev_page, id=photo_id)

# Make a tag request
@app.route('/tag_request', methods=['POST'])
def tag_request():
    username = session['username']
    tagged_user = request.form['tag-user']
    photo_id = int(request.form['photo-id'])
    prev_page = request.form['prev-page']
    cursor = conn.cursor()
    # check to see if user being tagged exists
    query = 'SELECT * FROM Person WHERE username = %s'
    cursor.execute(query, (tagged_user))
    data = cursor.fetchone()
    # if user exists
    if (data):
        # check to see if a tag request has already been made for this user photo combination
        query = 'SELECT * FROM Tagged WHERE username = %s AND photoID = %s'
        cursor.execute(query, (tagged_user, photo_id))
        data = cursor.fetchone()
        # tag already exists
        if (data):
            cursor.close()
            message = "User is already tagged in this photo."
            return render_template('message.html', id=photo_id, prev_page=prev_page, page='tag_user', message=message)
        else: # create tag request
            # check to see if photo is visible to tagged user 
            query = """(SELECT photoID, username_followed
                FROM Photo JOIN Follow ON (photoPoster = username_followed) 
                WHERE allFollowers = True AND followStatus = True AND photoID = %s AND username_follower = %s) UNION (
                SELECT photoID, member_username       
                FROM (BelongTo NATURAL JOIN SharedWith)  
                WHERE member_username = %s AND photoID = %s)"""
            cursor.execute(query, (photo_id, tagged_user, tagged_user, photo_id))
            data = cursor.fetchone()
            # if photo is visible to tagged user, make request
            if (data):
                query = 'INSERT INTO Tagged (username, photoID, tagstatus) VALUES(%s, %s, %s)'
                # if self-tag, set tagstatus to True, else set it False
                tagstatus = True if tagged_user == username else False
                cursor.execute(query, (tagged_user, photo_id, tagstatus))
                conn.commit()
                cursor.close()
                message = "Tag request successfully made!"
                return render_template('message.html', id=photo_id, prev_page=prev_page, page='tag_user', message=message)
            else: # photo is not visible to tagged user
                cursor.close()
                message = "Photo is not visible to that user."
                return render_template('message.html', id=photo_id, prev_page=prev_page, page='tag_user', message=message)
    else: # user does not exist
        cursor.close()
        message = "User does not exist."
        return render_template('message.html', id=photo_id, prev_page=prev_page, page='tag_user', message=message)

# View tag requests
@app.route('/view_tag_requests')
def view_tag_requests():
    username = session['username']
    cursor = conn.cursor()
    query = 'SELECT photoID, photoPoster FROM Tagged NATURAL JOIN Photo WHERE username = %s AND tagstatus = %s'
    cursor.execute(query, (username, False))
    conn.commit()
    data = cursor.fetchall()
    cursor.close()
    return render_template('view_tag_requests.html', requests=data)

# Accept tag request
@app.route('/accept_tag_request', methods=['POST'])
def accept_tag_request():
    username = session['username']
    photo_id = request.form['photo-id']
    cursor = conn.cursor()
    query = 'UPDATE Tagged SET tagstatus = %s WHERE username = %s AND photoID = %s'
    cursor.execute(query, (True, username, photo_id))
    conn.commit()
    cursor.close()
    message = 'You are now tagged in photo {}'.format(photo_id)
    return render_template('message.html', page="view_tag_request", message=message)

# Delete tag request
@app.route('/delete_tag_request', methods=['POST'])
def delete_tag_request():
    username = session['username']
    photo_id = request.form['photo-id']
    cursor = conn.cursor()
    query = 'DELETE FROM Tagged WHERE username = %s AND photoID = %s'
    cursor.execute(query, (username, photo_id))
    conn.commit()
    cursor.close()
    message = 'Deleted tag request for photo {}'.format(photo_id)
    return render_template('message.html', page="view_tag_request", message=message)

# Go to follow user page
@app.route('/follow_user')
def follow_user():
    return render_template('follow_user.html')

# Make follow request
@app.route('/follow_request', methods=['POST'])
def follow_request():
    username = session['username']
    username_followed = request.form['follow-user']
    cursor = conn.cursor()
    # check to see if username_followed exists
    query = 'SELECT * FROM Person WHERE username = %s'
    cursor.execute(query, (username_followed))
    data = cursor.fetchone()
    # if user exists
    if (data):
        # if requested user to follow is the same as follower
        if (data['username'] == username):
            message = "Can't follow yourself!"
            return render_template('follow_user.html', message=message)
        else:
            # check to see if user has already requested/is following username_followed
            query = 'SELECT * FROM Follow WHERE username_followed = %s AND username_follower = %s'
            cursor.execute(query, (username_followed, username))
            data = cursor.fetchone()
            # already following or requested
            if (data):
                message = "Already following" if data['followstatus'] else "Already requested."
                return render_template('follow_user.html', message=message)
            else: # make the request
                query = 'INSERT INTO Follow (username_followed, username_follower, followStatus) VALUES (%s, %s, %s)'
                cursor.execute(query, (username_followed, username, False))
                conn.commit()
                cursor.close()
                message = "Follow request sent!"
                return render_template('follow_user.html', message=message)
    else: # user does not exist
        message = "User does not exist."
        return render_template('follow_user.html', message=message)

# Go to view follow requests page
@app.route('/view_follow_requests')
def view_follow_requests():
    username = session['username']
    cursor = conn.cursor()
    query = 'SELECT username_follower FROM Follow WHERE username_followed = %s AND followstatus = %s'
    cursor.execute(query, (username, False))
    conn.commit()
    data = cursor.fetchall()
    cursor.close()
    return render_template('view_follow_requests.html', requests=data)

# Accept follow request
@app.route('/accept_follow_request', methods=['POST'])
def accept_request():
    username = session['username']
    username_follower = request.form['username_follower']
    cursor = conn.cursor()
    query = 'UPDATE Follow SET followstatus = %s WHERE username_followed = %s AND username_follower = %s'
    cursor.execute(query, (True, username, username_follower))
    conn.commit()
    cursor.close()
    message = '{} is now a follower!'.format(username_follower)
    return render_template('message.html', page='view_follow_request', message=message)

# Delete follow request
@app.route('/delete_follow_request', methods=['POST'])
def delete_request():
    username = session['username']
    username_follower = request.form['username_follower']
    cursor = conn.cursor()
    query = 'DELETE FROM Follow WHERE username_followed = %s AND username_follower = %s'
    cursor.execute(query, (username, username_follower))
    conn.commit()
    cursor.close()
    message = 'Follow request from {} has been deleted.'.format(username_follower)
    return render_template('message.html', page='view_follow_request', message=message)

@app.route('/view_photos', methods=["GET", "POST"])
def view_photos():
    #view all available photo info for current user
    username = session['username']
    cursor = conn.cursor()
    query = '''(SELECT DISTINCT photoID, photoPoster, filepath
        FROM Photo JOIN Follow ON (Photo.photoPoster = Follow.username_followed) 
        WHERE allFollowers = True AND username_follower = %s OR photoPoster = %s
        ORDER BY postingdate DESC) UNION
        (SELECT DISTINCT photoID, photoPoster, filepath
        FROM (Photo NATURAL JOIN SharedWith AS p1) 
        JOIN BelongTo ON (groupOwner = owner_username AND p1.groupName = BelongTo.groupName) 
        WHERE member_username = %s)'''
    cursor.execute(query, (username, username, username))
    conn.commit()
    data = cursor.fetchall()
    cursor.close()
    #modify the images' file path
    for item in data:
        item['filepath'] = url_for('static', filename=item['filepath'])
    return render_template('view_photos.html', posts=data)

#view detailed info of a post
@app.route('/view_info/<prev_page>/<photo_id>', methods=["GET", "POST"])
def view_info(photo_id, prev_page):
    cursor = conn.cursor()
    #fetch the photo info
    query_fetch = ''' SELECT postingdate, firstName, lastName, caption
        FROM Photo JOIN Person ON (Photo.photoPoster = Person.username)
        WHERE photoID = %s
            '''
    cursor.execute(query_fetch, (photo_id))
    conn.commit()
    data = cursor.fetchone()
    #fetech like info
    query_like = 'SELECT username, rating, liketime FROM Likes WHERE photoID = %s'
    cursor.execute(query_like, (photo_id))
    liked_by = cursor.fetchall()
    #fetech comments
    query_comment = 'SELECT username, comment, comment_time FROM Comments WHERE photoID = %s'
    cursor.execute(query_comment, (photo_id))
    comments = cursor.fetchall()
    #fetch stats
    query_stats = 'SELECT COUNT(*) AS total_like, ROUND(AVG(rating), 1) as avg_rating FROM Likes WHERE photoID = %s GROUP BY photoID'
    cursor.execute(query_stats, (photo_id))
    stat = cursor.fetchone()
    #fetch tagged
    query_tagged = 'SELECT username, firstName, lastName FROM Tagged NATURAL JOIN Person WHERE photoID = %s AND tagstatus = TRUE'
    cursor.execute(query_tagged, (photo_id))
    tagged = cursor.fetchall()
    cursor.close()
    return render_template('view_info.html', info=data, prev_page=prev_page, id=photo_id, liked_by=liked_by, comments=comments, stat=stat, tagged=tagged)

#Like a post
@app.route('/like', methods=["GET", "POST"])
def like():
    username = session['username']
    cursor = conn.cursor()
    photo_id = request.args.get('photoID')
    rating = request.form['rating'] 
    query = 'SELECT * FROM Likes WHERE username = %s AND photoID = %s'
    cursor.execute(query, (username, photo_id))
    message=""
    data = cursor.fetchone()
    #check if user already liked post
    if (data):
        if (data['username'] == username and data['photoID'] == int(photo_id)):
            message = "You have already liked and given this photo a rating!"
            return render_template('message.html', page='view_photos', message=message)
    else:
        query = 'INSERT INTO Likes (username, photoID, liketime, rating) VALUES (%s, %s, %s, %s)'
        message= "You successfully liked this post!"
        cursor.execute(query, (
            username, photo_id, time.strftime('%Y-%m-%d %H:%M:%S'), rating))
        conn.commit()
        cursor.close()
        return render_template('message.html', page='view_photos', message=message)

#Comment on a post
@app.route('/comment', methods=["GET", "POST"])
def comment():
    username = session['username']
    cursor = conn.cursor()
    photo_id = request.args.get('photoID')
    comment = request.form['comment']
    query = 'INSERT INTO Comments (username, photoID, comment_time, comment) VALUES (%s, %s, %s, %s)'
    cursor.execute(query, (username, photo_id, time.strftime('%Y-%m-%d %H:%M:%S'), comment))
    conn.commit()
    cursor.close()
    message = "You successfully commented on this post!"
    return render_template('message.html', page='view_photos', message=message)

@app.route('/logout')
def logout():
    session.pop('username')
    return redirect('/')
        
app.secret_key = 'some key that you will never guess'
#Run the app on localhost port 5000
#debug = True -> you don't have to restart flask
#for changes to go through, TURN OFF FOR PRODUCTION
if __name__ == "__main__":
    app.run('127.0.0.1', 5000, debug = True)

