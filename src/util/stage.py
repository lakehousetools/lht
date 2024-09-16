import io
import os

def put_file(session, stage, file):
    # Create an in-memory file object
    file_obj = io.BytesIO(file)

    # Create a temporary file in the filesystem and upload it
    import tempfile
    import shutil

    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        shutil.copyfileobj(file_obj, temp_file)
        temp_file_path = temp_file.name

    # Use Snowflake's PUT command to upload the temporary file to the stage
    put_command = f"PUT file://{temp_file_path} @{}".format(stage)

    session.execute(put_command)

    # Clean up temporary file
    os.remove(temp_file_path)

    session.close()