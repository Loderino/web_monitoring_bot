import setuptools

setuptools.setup(
    name="web_monitoring_bot",
    version="0.0.1",
    packages=setuptools.find_packages(),
    install_requires=[
        "apscheduler==3.11.0",
        "httpx==0.28.1",
        "pymongo==4.15.1",
        "python-dotenv==1.1.1",
        "python-telegram-bot==22.4",
    ],
    python_requires=">=3.11",
)
