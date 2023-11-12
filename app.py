import tkinter as tk
from tkinter import filedialog
from threading import Thread
import os
import mimetypes
import pathlib
from pathlib import Path
import boto3
from botocore.exceptions import ClientError
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from tkinter import messagebox


def read_files_from_location(local_path):
    file_paths = Path(local_path)
    return list([entry.name for entry in file_paths.iterdir() if entry.is_dir()])

def map_path_to_file(directories, local_path):
    file_dicts = {}
    for d in directories:
        file_paths = Path("".join([local_path, f'\\{d}'])).rglob("*")

        for file_path in file_paths:
            if file_path.is_file():
                full_file_name, file_name, file_extension = file_path.name, file_path.stem, file_path.suffix
                file_path, parent_directory = str(file_path.parent), file_path.parent.name
                content_type = mimetypes.guess_type(full_file_name)[0]
                file_size = os.path.getsize("".join([file_path, '\\', full_file_name]))
                posix_path = pathlib.PureWindowsPath(file_path)
                relative_path = str(posix_path.relative_to(local_path))

                files_arr = []
                file_metadata_dict = {
                    'full_file_name': full_file_name,
                    'file_name': file_name,
                    'file_extension': file_extension,
                    'absolute_path': file_path,
                    'parent_directory': parent_directory,
                    'content_type': content_type,
                    'file_size': file_size,
                    'relative_path': relative_path
                }

                files_arr.append(file_metadata_dict)

                if d in file_dicts:
                    file_dicts[d].append(file_metadata_dict)
                else:
                    file_dicts[d] = files_arr

    return file_dicts

import concurrent.futures

# Modify the upload_to_s3 function to accept a single file and upload it
def upload_file_to_s3(file, aws_access_key_id, aws_secret_access_key, bucket_name):
    s3_client = boto3.client('s3', aws_access_key_id=aws_access_key_id,
                             aws_secret_access_key=aws_secret_access_key)

    file_name, relative_path, absolute_path = file['full_file_name'], file['relative_path'], file['absolute_path']
    source_path = ''.join([absolute_path, '\\', file_name])
    s3_destination_path = ''.join([relative_path.replace('\\', '/'), '/', file_name])

    try:
        with open(source_path, 'rb') as data:
            s3_client.upload_fileobj(data, bucket_name, s3_destination_path)
    except (ClientError, FileNotFoundError) as e:
        print(e)


# Modify the upload_to_s3 function to use multi-threading
def upload_to_s3(file_dicts, aws_access_key_id, aws_secret_access_key, bucket_name, batch_size=10):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []

        for file_dict in file_dicts:
            batch = file_dicts.get(file_dict)
            for i in range(0, len(batch), batch_size):
                files_to_upload = batch[i:i + batch_size]
                futures.extend(executor.submit(upload_file_to_s3, file, aws_access_key_id, aws_secret_access_key, bucket_name) for file in files_to_upload)

        concurrent.futures.wait(futures)


# Rest of your code remains unchanged



class MyHandler(FileSystemEventHandler):
    def __init__(self, local_path, aws_access_key_id, aws_secret_access_key, bucket_name):
        self.local_path = local_path
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.bucket_name = bucket_name
        super().__init__()

    def on_modified(self, event):
        if event.is_directory:
            # Directory modified, upload files from this directory
            directory = read_files_from_location(self.local_path)
            file_dicts_response = map_path_to_file(directory, self.local_path)
            upload_to_s3(file_dicts_response, self.aws_access_key_id, self.aws_secret_access_key, self.bucket_name)
        elif event.event_type == 'modified':
            # File modified, upload this file
            file_path = Path(event.src_path)
            directory_name = file_path.parent.name
            file_dicts_response = map_path_to_file([directory_name], self.local_path)
            upload_to_s3(file_dicts_response, self.aws_access_key_id, self.aws_secret_access_key, self.bucket_name)

def start_monitoring(local_path, aws_access_key_id, aws_secret_access_key, bucket_name):
    observer = Observer()
    event_handler = MyHandler(local_path, aws_access_key_id, aws_secret_access_key, bucket_name)
    observer.schedule(event_handler, path=local_path, recursive=True)
    observer.start()
    try:
        while True:
            pass
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

def on_connect_click():
    local_path = local_path_entry.get()
    aws_access_key_id = aws_access_key_id_entry.get()
    aws_secret_access_key = aws_secret_access_key_entry.get()
    bucket_name = bucket_name_entry.get()
    
    try:
        # Validate inputs
        if not local_path or not aws_access_key_id or not aws_secret_access_key or not bucket_name:
            messagebox.showerror("Error", "All fields are required!")
        else:
            start_monitoring(local_path, aws_access_key_id, aws_secret_access_key, bucket_name)
    except Exception as e:
        messagebox.showerror("Error", str(e))

# GUI setup
root = tk.Tk()
root.title("S3 Uploader")

local_path_label = tk.Label(root, text="Local Folder Path:")
local_path_label.pack()
local_path_entry = tk.Entry(root, width=50)
local_path_entry.pack()

aws_access_key_id_label = tk.Label(root, text="AWS Access Key ID:")
aws_access_key_id_label.pack()
aws_access_key_id_entry = tk.Entry(root, width=50)
aws_access_key_id_entry.pack()

aws_secret_access_key_label = tk.Label(root, text="AWS Secret Access Key:")
aws_secret_access_key_label.pack()
aws_secret_access_key_entry = tk.Entry(root, width=50, show="*")
aws_secret_access_key_entry.pack()

bucket_name_label = tk.Label(root, text="Bucket Name:")
bucket_name_label.pack()
bucket_name_entry = tk.Entry(root, width=50)
bucket_name_entry.pack()

connect_button = tk.Button(root, text="Connect", command=on_connect_click)
connect_button.pack()

root.mainloop()