import PyInstaller.__main__
import os

PyInstaller.__main__.run([
    'aur_manager.py',
    '--name=oracle',
    '--onefile',
    '--windowed',
    '--clean',
    '--noupx',
]) 