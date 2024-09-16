import os
from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from spotipy.cache_handler import FlaskSessionCacheHandler
from dotenv import load_dotenv

# Load environment variables from a .env file
load_dotenv()

# Initialize Flask application
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(64)  # Set a random secret key for session management

# Retrieve Spotify credentials and settings from environment variables
client_id = os.getenv('SPOTIPY_CLIENT_ID')
client_secret = os.getenv('SPOTIPY_CLIENT_SECRET')
redirect_uri = 'http://localhost:5000/callback'
scope = 'playlist-read-private playlist-modify-public playlist-modify-private'

# Initialize cache handler for Spotify OAuth
cache_handler = FlaskSessionCacheHandler(session)

# Set up SpotifyOAuth instance for authorization
sp_oauth = SpotifyOAuth(
    client_id=client_id,
    client_secret=client_secret,
    redirect_uri=redirect_uri,
    scope=scope,
    cache_handler=cache_handler,
    show_dialog=True
)

# Create a Spotify instance with the OAuth manager
sp = Spotify(auth_manager=sp_oauth)

# Route for the home page
@app.route('/')
def home():
    # Check if the token is valid, if not redirect to Spotify authorization
    if not sp_oauth.validate_token(cache_handler.get_cached_token()):
        auth_url = sp_oauth.get_authorize_url()
        return redirect(auth_url)
    return render_template('index.html')

# Route for handling the callback from Spotify authorization
@app.route('/callback')
def callback():
    # Exchange authorization code for an access token
    token_info = sp_oauth.get_access_token(request.args.get('code'))
    if not token_info:
        flash("Authorization failed. Please try again.")
        return redirect(url_for('home'))
    return redirect(url_for('home'))

# Route to fetch user's playlists
@app.route('/fetch_playlists')
def fetch_playlists():
    # Check if the token is valid, if not redirect to Spotify authorization
    if not sp_oauth.validate_token(cache_handler.get_cached_token()):
        auth_url = sp_oauth.get_authorize_url()
        return redirect(auth_url)

    try:
        # Fetch the user's playlists
        playlists = sp.current_user_playlists()
        # Extract playlist names and URLs
        playlists_info = [(pl['name'], pl['external_urls']['spotify']) for pl in playlists['items']]
    except Exception as e:
        flash(f"Failed to fetch playlists: {str(e)}")
        return redirect(url_for('home'))

    # Return playlist information as JSON
    return jsonify(playlists_info)

# Route to merge selected playlists
@app.route('/merge_playlists', methods=['POST'])
def merge_playlists():
    # Retrieve number of playlists and their URLs from the form
    number_of_playlists = int(request.form['numberOfPlaylists'])
    playlist_urls = [request.form[f'playlist{i+1}'] for i in range(number_of_playlists)]

    playlist_names = []
    for url in playlist_urls:
        playlist_id = url.split('/')[-1].split('?')[0]
        playlist_info = sp.playlist(playlist_id)
        playlist_names.append(playlist_info['name'])

    # Create a new playlist with a name indicating the merge
    playlist_name = "Merge of " + ", ".join(playlist_names)
    user_id = sp.current_user()['id']

    try:
        # Create a new playlist for the merged tracks
        new_playlist = sp.user_playlist_create(
            user=user_id,
            name=playlist_name,
            description="Merged playlist of selected playlists"
        )
        new_playlist_id = new_playlist['id']

        track_uris = []
        for url in playlist_urls:
            playlist_id = url.split('/')[-1].split('?')[0]
            results = sp.playlist_tracks(playlist_id)
            if results['items']:
                for item in results['items']:
                    track = item['track']
                    track_uris.append(track['uri'])

        if not track_uris:
            flash("No tracks found in selected playlists.")
            return redirect(url_for('home'))

        # Add tracks to the new playlist in chunks of 100 (Spotify API limit)
        for i in range(0, len(track_uris), 100):
            sp.playlist_add_items(new_playlist_id, track_uris[i:i+100])

        flash("Playlists merged successfully!")
    except Exception as e:
        flash(f"Failed to merge playlists: {str(e)}")

    return redirect(url_for('home'))

# Route to log out and clear the session
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# Run the Flask application
if __name__ == '__main__':
    app.run(debug=True)
