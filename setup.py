from setuptools import setup, Extension, find_packages
from setuptools.command.build_py import build_py
from wheel.bdist_wheel import bdist_wheel
from Cython.Build import cythonize
from Cython.Distutils import build_ext as CythonBuildExt
import os
import glob
import shutil
import zipfile
import tempfile

class BuildPyWithoutSources(build_py):
    """Allow all files during build (for compilation), filtering happens in wheel"""
    pass

class BdistWheelWithoutSources(bdist_wheel):
    """Custom bdist_wheel that excludes .py files except __init__.py from wheel"""
    def run(self):
        # Run parent to create wheel
        super().run()
        
        # Find and filter the wheel file
        if hasattr(self, 'dist_dir'):
            wheel_path = None
            for file in os.listdir(self.dist_dir):
                if file.endswith('.whl'):
                    wheel_path = os.path.join(self.dist_dir, file)
                    break
            
            if wheel_path:
                # Extract, filter, and rezip
                import hashlib
                
                with tempfile.TemporaryDirectory() as tmpdir:
                    extract_dir = os.path.join(tmpdir, 'extract')
                    os.makedirs(extract_dir)
                    
                    with zipfile.ZipFile(wheel_path, 'r') as zin:
                        # Find the dist-info directory name first
                        dist_info_dir = None
                        for item in zin.infolist():
                            if '.dist-info/' in item.filename and item.filename.endswith('/METADATA'):
                                dist_info_dir = item.filename.split('/')[0]
                                break
                        
                        # Extract all files first
                        zin.extractall(extract_dir)
                    
                    # Now create new wheel with filtered files
                    with zipfile.ZipFile(os.path.join(tmpdir, 'new.whl'), 'w', zipfile.ZIP_DEFLATED) as zout:
                        record_entries = []
                        
                        # Walk through extracted files
                        for root, dirs, files in os.walk(extract_dir):
                            for file in files:
                                file_path = os.path.join(root, file)
                                # Get relative path within wheel
                                rel_path = os.path.relpath(file_path, extract_dir).replace(os.sep, '/')
                                
                                # Skip .py files except __init__.py
                                if rel_path.endswith('.py') and not rel_path.endswith('__init__.py'):
                                    continue
                                
                                # Skip RECORD file - we'll regenerate it
                                if rel_path.endswith('.dist-info/RECORD'):
                                    continue
                                
                                # Read file content
                                with open(file_path, 'rb') as f:
                                    data = f.read()
                                
                                # Write to new wheel
                                zout.writestr(rel_path, data)
                                
                                # Calculate hash for RECORD file
                                hash_obj = hashlib.sha256(data)
                                hash_value = hash_obj.hexdigest()
                                record_entries.append(f"{rel_path},sha256={hash_value},{len(data)}")
                        
                        # Sort record entries for consistency
                        record_entries.sort()
                        
                        if dist_info_dir:
                            # Add RECORD file itself (without hash/size for RECORD entry)
                            record_path = f"{dist_info_dir}/RECORD"
                            record_content = '\n'.join(record_entries)
                            if record_content:  # Add newline if there are entries
                                record_content += '\n'
                            record_content += f"{record_path},,\n"
                            
                            # Write RECORD file to wheel
                            zout.writestr(record_path, record_content.encode('utf-8'))
                    
                    # Replace original wheel
                    shutil.move(os.path.join(tmpdir, 'new.whl'), wheel_path)

def find_py_files():
    """Find all Python files to compile with Cython"""
    extensions = []
    
    # Walk through the src/lht directory
    for root, dirs, files in os.walk('src/lht'):
        # Skip __pycache__ directories
        dirs[:] = [d for d in dirs if d != '__pycache__']
        
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                
                # Convert file path to module name
                # Example: src/lht/util/data_writer.py -> lht.util.data_writer
                rel_path = file_path.replace('src/', '').replace('/', '.').replace('.py', '')
                
                extensions.append(Extension(
                    rel_path,
                    [file_path],
                    language='c'
                ))
    
    return extensions

# Get all extensions
extensions = find_py_files()

# Configure Cython compilation
extensions = cythonize(
    extensions,
    compiler_directives={
        'language_level': "3",  # Python 3
        'boundscheck': False,    # Disable bounds checking for speed
        'wraparound': True,      # Enable negative index wrapping (required for Python compatibility)
        'cdivision': True,       # Use C division semantics
    },
    build_dir='build',
    annotate=True  # Generate HTML annotation files for optimization (set to False to disable)
)

setup(
    ext_modules=extensions,
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    cmdclass={
        'build_ext': CythonBuildExt,
        'build_py': BuildPyWithoutSources,
        'bdist_wheel': BdistWheelWithoutSources,
    },
    zip_safe=False,  # Required for Cython
)
