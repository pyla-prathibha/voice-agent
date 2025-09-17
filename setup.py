"""
Setup script for Voice Agent package.
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="voice-agent",
    version="1.0.0",
    author="Voice Agent Team",
    author_email="contact@voiceagent.ai",
    description="Real-time voice interaction system using Plivo, ElevenLabs, and OpenAI GPT",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/pyla-prathibha/voice-agent",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Communications :: Telephony",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "voice-agent=main:main",
        ],
    },
    keywords="voice ai assistant telephony plivo elevenlabs openai gpt speech recognition text-to-speech",
    project_urls={
        "Bug Reports": "https://github.com/pyla-prathibha/voice-agent/issues",
        "Source": "https://github.com/pyla-prathibha/voice-agent",
        "Documentation": "https://github.com/pyla-prathibha/voice-agent#readme",
    },
)