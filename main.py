
import os
import time
import threading
import glob
from flask import Flask, render_template, request, jsonify, send_file, after_this_request
import yt_dlp

app = Flask(__name__)

# ফোল্ডার কনফিগারেশন
DOWNLOAD_FOLDER = 'downloads'
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# অটোমেটিক ফাইল ডিলেট করার ফাংশন (৭ মিনিট পর)
def cleanup_old_files():
    while True:
        now = time.time()
        # ৭ মিনিট = ৪২০ সেকেন্ড
        cutoff = now - 420 
        files = glob.glob(os.path.join(DOWNLOAD_FOLDER, "*"))
        for f in files:
            if os.stat(f).st_mtime < cutoff:
                try:
                    os.remove(f)
                    print(f"Deleted old file: {f}")
                except Exception as e:
                    print(f"Error deleting file: {e}")
        time.sleep(60) # প্রতি ১ মিনিটে চেক করবে

# ব্যাকগ্রাউন্ডে ক্লিনআপ থ্রেড রান করা
cleanup_thread = threading.Thread(target=cleanup_old_files, daemon=True)
cleanup_thread.start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get-info', methods=['POST'])
def get_info():
    url = request.json.get('url')
    if not url:
        return jsonify({'error': 'No URL provided'}), 400

    try:
        ydl_opts = {'quiet': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = []
            
            # ফরম্যাট ফিল্টার করা (শুধুমাত্র ভিডিও এবং mp4)
            seen_resolutions = set()
            for f in info.get('formats', []):
                # ফেসবুকের জন্য mp4 এবং হাইট চেক করা
                if f.get('ext') == 'mp4' and f.get('height'):
                    resolution = f"{f.get('height')}p"
                    if resolution not in seen_resolutions:
                        formats.append({
                            'format_id': f['format_id'],
                            'resolution': resolution,
                            'ext': f['ext'],
                            'note': f.get('format_note', '')
                        })
                        seen_resolutions.add(resolution)
            
            # রেজোলিউশন অনুযায়ী সর্ট করা (বড় থেকে ছোট)
            formats.sort(key=lambda x: int(x['resolution'].replace('p', '')), reverse=True)

            return jsonify({
                'title': info.get('title', 'Video'),
                'thumbnail': info.get('thumbnail'),
                'formats': formats
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/process-download', methods=['POST'])
def process_download():
    data = request.json
    url = data.get('url')
    format_id = data.get('format_id')
    
    filename_template = f"{DOWNLOAD_FOLDER}/%(title)s_%(id)s.%(ext)s"

    ydl_opts = {
        'format': format_id + '+bestaudio/best', # ভিডিও + বেস্ট অডিও
        'outtmpl': filename_template,
        'merge_output_format': 'mp4',
        'quiet': True
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            # যদি মার্জ হয়, এক্সটেনশন .mp4 হতে পারে
            if not os.path.exists(filename):
                 filename = os.path.splitext(filename)[0] + ".mp4"
            
            return jsonify({'status': 'ready', 'filename': os.path.basename(filename)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download/<path:filename>')
def download_file(filename):
    file_path = os.path.join(DOWNLOAD_FOLDER, filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    else:
        return "File not found or expired", 404

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
