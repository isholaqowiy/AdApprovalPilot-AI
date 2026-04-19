==> Downloading cache...
==> Cloning from https://github.com/isholaqowiy/AdApprovalPilot-AI
==> Checking out commit ff5d7334608d1dad749e2351518c2d6dc3fdca03 in branch main
==> Downloaded 97MB in 3s. Extraction took 1s.
==> Using Python version 3.12.2 via environment variable PYTHON_VERSION
==> Docs on specifying a Python version: https://render.com/docs/python-version
Menu
==> Installing Python version 3.12.2...
==> Using Poetry version 2.1.3 (default)
==> Docs on specifying a Poetry version: https://render.com/docs/poetry-version
==> Running build command 'pip install -r requirements.txt'...
Collecting python-telegram-bot>=21.0 (from python-telegram-bot[job-queue]>=21.0->-r requirements.txt (line 1))
  Using cached python_telegram_bot-22.7-py3-none-any.whl.metadata (17 kB)
Collecting flask==3.0.2 (from -r requirements.txt (line 2))
  Using cached flask-3.0.2-py3-none-any.whl.metadata (3.6 kB)
Collecting gunicorn==21.2.0 (from -r requirements.txt (line 3))
  Using cached gunicorn-21.2.0-py3-none-any.whl.metadata (4.1 kB)
Collecting httpx==0.27.0 (from -r requirements.txt (line 4))
  Using cached httpx-0.27.0-py3-none-any.whl.metadata (7.2 kB)
Collecting google-generativeai>=0.5.0 (from -r requirements.txt (line 5))
  Using cached google_generativeai-0.8.6-py3-none-any.whl.metadata (3.9 kB)
Collecting Werkzeug>=3.0.0 (from flask==3.0.2->-r requirements.txt (line 2))
  Using cached werkzeug-3.1.8-py3-none-any.whl.metadata (4.0 kB)
Collecting Jinja2>=3.1.2 (from flask==3.0.2->-r requirements.txt (line 2))
  Using cached jinja2-3.1.6-py3-none-any.whl.metadata (2.9 kB)
Collecting itsdangerous>=2.1.2 (from flask==3.0.2->-r requirements.txt (line 2))
  Using cached itsdangerous-2.2.0-py3-none-any.whl.metadata (1.9 kB)
Collecting click>=8.1.3 (from flask==3.0.2->-r requirements.txt (line 2))
  Using cached click-8.3.2-py3-none-any.whl.metadata (2.6 kB)
Collecting blinker>=1.6.2 (from flask==3.0.2->-r requirements.txt (line 2))
  Using cached blinker-1.9.0-py3-none-any.whl.metadata (1.6 kB)
Collecting packaging (from gunicorn==21.2.0->-r requirements.txt (line 3))
  Using cached packaging-26.1-py3-none-any.whl.metadata (3.5 kB)
Collecting anyio (from httpx==0.27.0->-r requirements.txt (line 4))
  Using cached anyio-4.13.0-py3-none-any.whl.metadata (4.5 kB)
Collecting certifi (from httpx==0.27.0->-r requirements.txt (line 4))
  Using cached certifi-2026.2.25-py3-none-any.whl.metadata (2.5 kB)
Collecting httpcore==1.* (from httpx==0.27.0->-r requirements.txt (line 4))
  Using cached httpcore-1.0.9-py3-none-any.whl.metadata (21 kB)
Collecting idna (from httpx==0.27.0->-r requirements.txt (line 4))
  Using cached idna-3.11-py3-none-any.whl.metadata (8.4 kB)
Collecting sniffio (from httpx==0.27.0->-r requirements.txt (line 4))
  Using cached sniffio-1.3.1-py3-none-any.whl.metadata (3.9 kB)
Collecting h11>=0.16 (from httpcore==1.*->httpx==0.27.0->-r requirements.txt (line 4))
  Using cached h11-0.16.0-py3-none-any.whl.metadata (8.3 kB)
Collecting google-ai-generativelanguage==0.6.15 (from google-generativeai>=0.5.0->-r requirements.txt (line 5))
  Using cached google_ai_generativelanguage-0.6.15-py3-none-any.whl.metadata (5.7 kB)
Collecting google-api-core (from google-generativeai>=0.5.0->-r requirements.txt (line 5))
  Using cached google_api_core-2.30.3-py3-none-any.whl.metadata (3.1 kB)
Collecting google-api-python-client (from google-generativeai>=0.5.0->-r requirements.txt (line 5))
  Using cached google_api_python_client-2.194.0-py3-none-any.whl.metadata (7.0 kB)
Collecting google-auth>=2.15.0 (from google-generativeai>=0.5.0->-r requirements.txt (line 5))
  Using cached google_auth-2.49.2-py3-none-any.whl.metadata (6.2 kB)
Collecting protobuf (from google-generativeai>=0.5.0->-r requirements.txt (line 5))
  Using cached protobuf-7.34.1-cp310-abi3-manylinux2014_x86_64.whl.metadata (595 bytes)
Collecting pydantic (from google-generativeai>=0.5.0->-r requirements.txt (line 5))
  Using cached pydantic-2.13.2-py3-none-any.whl.metadata (108 kB)
Collecting tqdm (from google-generativeai>=0.5.0->-r requirements.txt (line 5))
  Using cached tqdm-4.67.3-py3-none-any.whl.metadata (57 kB)
Collecting typing-extensions (from google-generativeai>=0.5.0->-r requirements.txt (line 5))
  Using cached typing_extensions-4.15.0-py3-none-any.whl.metadata (3.3 kB)
Collecting proto-plus<2.0.0dev,>=1.22.3 (from google-ai-generativelanguage==0.6.15->google-generativeai>=0.5.0->-r requirements.txt (line 5))
  Using cached proto_plus-1.27.2-py3-none-any.whl.metadata (2.2 kB)
Collecting protobuf (from google-generativeai>=0.5.0->-r requirements.txt (line 5))
  Using cached protobuf-5.29.6-cp38-abi3-manylinux2014_x86_64.whl.metadata (592 bytes)
Collecting apscheduler<3.12.0,>=3.10.4 (from python-telegram-bot[job-queue]>=21.0->-r requirements.txt (line 1))
  Using cached apscheduler-3.11.2-py3-none-any.whl.metadata (6.4 kB)
Collecting tzlocal>=3.0 (from apscheduler<3.12.0,>=3.10.4->python-telegram-bot[job-queue]>=21.0->-r requirements.txt (line 1))
  Using cached tzlocal-5.3.1-py3-none-any.whl.metadata (7.6 kB)
Collecting googleapis-common-protos<2.0.0,>=1.63.2 (from google-api-core->google-generativeai>=0.5.0->-r requirements.txt (line 5))
  Using cached googleapis_common_protos-1.74.0-py3-none-any.whl.metadata (9.2 kB)
Collecting requests<3.0.0,>=2.20.0 (from google-api-core->google-generativeai>=0.5.0->-r requirements.txt (line 5))
  Using cached requests-2.33.1-py3-none-any.whl.metadata (4.8 kB)
Collecting pyasn1-modules>=0.2.1 (from google-auth>=2.15.0->google-generativeai>=0.5.0->-r requirements.txt (line 5))
  Using cached pyasn1_modules-0.4.2-py3-none-any.whl.metadata (3.5 kB)
Collecting cryptography>=38.0.3 (from google-auth>=2.15.0->google-generativeai>=0.5.0->-r requirements.txt (line 5))
  Using cached cryptography-46.0.7-cp311-abi3-manylinux_2_34_x86_64.whl.metadata (5.7 kB)
Collecting MarkupSafe>=2.0 (from Jinja2>=3.1.2->flask==3.0.2->-r requirements.txt (line 2))
  Using cached markupsafe-3.0.3-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl.metadata (2.7 kB)
Collecting httplib2<1.0.0,>=0.19.0 (from google-api-python-client->google-generativeai>=0.5.0->-r requirements.txt (line 5))
  Using cached httplib2-0.31.2-py3-none-any.whl.metadata (2.2 kB)
Collecting google-auth-httplib2<1.0.0,>=0.2.0 (from google-api-python-client->google-generativeai>=0.5.0->-r requirements.txt (line 5))
  Using cached google_auth_httplib2-0.3.1-py3-none-any.whl.metadata (3.0 kB)
Collecting uritemplate<5,>=3.0.1 (from google-api-python-client->google-generativeai>=0.5.0->-r requirements.txt (line 5))
  Using cached uritemplate-4.2.0-py3-none-any.whl.metadata (2.6 kB)
Collecting annotated-types>=0.6.0 (from pydantic->google-generativeai>=0.5.0->-r requirements.txt (line 5))
  Using cached annotated_types-0.7.0-py3-none-any.whl.metadata (15 kB)
Collecting pydantic-core==2.46.2 (from pydantic->google-generativeai>=0.5.0->-r requirements.txt (line 5))
  Using cached pydantic_core-2.46.2-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (6.6 kB)
Collecting typing-inspection>=0.4.2 (from pydantic->google-generativeai>=0.5.0->-r requirements.txt (line 5))
  Using cached typing_inspection-0.4.2-py3-none-any.whl.metadata (2.6 kB)
Collecting cffi>=2.0.0 (from cryptography>=38.0.3->google-auth>=2.15.0->google-generativeai>=0.5.0->-r requirements.txt (line 5))
  Using cached cffi-2.0.0-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.whl.metadata (2.6 kB)
Collecting grpcio<2.0.0,>=1.33.2 (from google-api-core[grpc]!=2.0.*,!=2.1.*,!=2.10.*,!=2.2.*,!=2.3.*,!=2.4.*,!=2.5.*,!=2.6.*,!=2.7.*,!=2.8.*,!=2.9.*,<3.0.0dev,>=1.34.1->google-ai-generativelanguage==0.6.15->google-generativeai>=0.5.0->-r requirements.txt (line 5))
  Using cached grpcio-1.80.0-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.whl.metadata (3.8 kB)
Collecting grpcio-status<2.0.0,>=1.33.2 (from google-api-core[grpc]!=2.0.*,!=2.1.*,!=2.10.*,!=2.2.*,!=2.3.*,!=2.4.*,!=2.5.*,!=2.6.*,!=2.7.*,!=2.8.*,!=2.9.*,<3.0.0dev,>=1.34.1->google-ai-generativelanguage==0.6.15->google-generativeai>=0.5.0->-r requirements.txt (line 5))
  Using cached grpcio_status-1.80.0-py3-none-any.whl.metadata (1.3 kB)
Collecting pyparsing<4,>=3.1 (from httplib2<1.0.0,>=0.19.0->google-api-python-client->google-generativeai>=0.5.0->-r requirements.txt (line 5))
  Using cached pyparsing-3.3.2-py3-none-any.whl.metadata (5.8 kB)
Collecting pyasn1<0.7.0,>=0.6.1 (from pyasn1-modules>=0.2.1->google-auth>=2.15.0->google-generativeai>=0.5.0->-r requirements.txt (line 5))
  Using cached pyasn1-0.6.3-py3-none-any.whl.metadata (8.4 kB)
Collecting charset_normalizer<4,>=2 (from requests<3.0.0,>=2.20.0->google-api-core->google-generativeai>=0.5.0->-r requirements.txt (line 5))
  Using cached charset_normalizer-3.4.7-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl.metadata (40 kB)
Collecting urllib3<3,>=1.26 (from requests<3.0.0,>=2.20.0->google-api-core->google-generativeai>=0.5.0->-r requirements.txt (line 5))
  Using cached urllib3-2.6.3-py3-none-any.whl.metadata (6.9 kB)
Collecting pycparser (from cffi>=2.0.0->cryptography>=38.0.3->google-auth>=2.15.0->google-generativeai>=0.5.0->-r requirements.txt (line 5))
  Using cached pycparser-3.0-py3-none-any.whl.metadata (8.2 kB)
INFO: pip is looking at multiple versions of grpcio-status to determine which version is compatible with other requirements. This could take a while.
Collecting grpcio-status<2.0.0,>=1.33.2 (from google-api-core[grpc]!=2.0.*,!=2.1.*,!=2.10.*,!=2.2.*,!=2.3.*,!=2.4.*,!=2.5.*,!=2.6.*,!=2.7.*,!=2.8.*,!=2.9.*,<3.0.0dev,>=1.34.1->google-ai-generativelanguage==0.6.15->google-generativeai>=0.5.0->-r requirements.txt (line 5))
  Using cached grpcio_status-1.78.0-py3-none-any.whl.metadata (1.3 kB)
  Using cached grpcio_status-1.76.0-py3-none-any.whl.metadata (1.1 kB)
  Using cached grpcio_status-1.75.1-py3-none-any.whl.metadata (1.1 kB)
  Using cached grpcio_status-1.75.0-py3-none-any.whl.metadata (1.1 kB)
  Using cached grpcio_status-1.74.0-py3-none-any.whl.metadata (1.1 kB)
  Using cached grpcio_status-1.73.1-py3-none-any.whl.metadata (1.1 kB)
  Using cached grpcio_status-1.73.0-py3-none-any.whl.metadata (1.1 kB)
INFO: pip is still looking at multiple versions of grpcio-status to determine which version is compatible with other requirements. This could take a while.
  Using cached grpcio_status-1.72.2-py3-none-any.whl.metadata (1.1 kB)
  Using cached grpcio_status-1.72.1-py3-none-any.whl.metadata (1.1 kB)
  Using cached grpcio_status-1.71.2-py3-none-any.whl.metadata (1.1 kB)
Using cached flask-3.0.2-py3-none-any.whl (101 kB)
Using cached gunicorn-21.2.0-py3-none-any.whl (80 kB)
Using cached httpx-0.27.0-py3-none-any.whl (75 kB)
Using cached httpcore-1.0.9-py3-none-any.whl (78 kB)
Using cached python_telegram_bot-22.7-py3-none-any.whl (745 kB)
Using cached google_generativeai-0.8.6-py3-none-any.whl (155 kB)
Using cached google_ai_generativelanguage-0.6.15-py3-none-any.whl (1.3 MB)
Using cached apscheduler-3.11.2-py3-none-any.whl (64 kB)
Using cached blinker-1.9.0-py3-none-any.whl (8.5 kB)
Using cached click-8.3.2-py3-none-any.whl (108 kB)
Using cached google_api_core-2.30.3-py3-none-any.whl (173 kB)
Using cached google_auth-2.49.2-py3-none-any.whl (240 kB)
Using cached itsdangerous-2.2.0-py3-none-any.whl (16 kB)
Using cached jinja2-3.1.6-py3-none-any.whl (134 kB)
Using cached protobuf-5.29.6-cp38-abi3-manylinux2014_x86_64.whl (320 kB)
Using cached werkzeug-3.1.8-py3-none-any.whl (226 kB)
Using cached anyio-4.13.0-py3-none-any.whl (114 kB)
Using cached idna-3.11-py3-none-any.whl (71 kB)
Using cached typing_extensions-4.15.0-py3-none-any.whl (44 kB)
Using cached certifi-2026.2.25-py3-none-any.whl (153 kB)
Using cached google_api_python_client-2.194.0-py3-none-any.whl (15.0 MB)
Using cached packaging-26.1-py3-none-any.whl (95 kB)
Using cached pydantic-2.13.2-py3-none-any.whl (471 kB)
Using cached pydantic_core-2.46.2-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (2.1 MB)
Using cached sniffio-1.3.1-py3-none-any.whl (10 kB)
Using cached tqdm-4.67.3-py3-none-any.whl (78 kB)
Using cached annotated_types-0.7.0-py3-none-any.whl (13 kB)
Using cached cryptography-46.0.7-cp311-abi3-manylinux_2_34_x86_64.whl (4.5 MB)
Using cached google_auth_httplib2-0.3.1-py3-none-any.whl (9.5 kB)
Using cached googleapis_common_protos-1.74.0-py3-none-any.whl (300 kB)
Using cached h11-0.16.0-py3-none-any.whl (37 kB)
Using cached httplib2-0.31.2-py3-none-any.whl (91 kB)
Using cached markupsafe-3.0.3-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl (22 kB)
Using cached proto_plus-1.27.2-py3-none-any.whl (50 kB)
Using cached pyasn1_modules-0.4.2-py3-none-any.whl (181 kB)
Using cached requests-2.33.1-py3-none-any.whl (64 kB)
Using cached typing_inspection-0.4.2-py3-none-any.whl (14 kB)
Using cached tzlocal-5.3.1-py3-none-any.whl (18 kB)
Using cached uritemplate-4.2.0-py3-none-any.whl (11 kB)
Using cached cffi-2.0.0-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.whl (219 kB)
Using cached charset_normalizer-3.4.7-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl (216 kB)
Using cached grpcio-1.80.0-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.whl (6.8 MB)
Using cached grpcio_status-1.71.2-py3-none-any.whl (14 kB)
Using cached pyasn1-0.6.3-py3-none-any.whl (83 kB)
Using cached pyparsing-3.3.2-py3-none-any.whl (122 kB)
Using cached urllib3-2.6.3-py3-none-any.whl (131 kB)
Using cached pycparser-3.0-py3-none-any.whl (48 kB)
Installing collected packages: urllib3, uritemplate, tzlocal, typing-extensions, tqdm, sniffio, pyparsing, pycparser, pyasn1, protobuf, packaging, MarkupSafe, itsdangerous, idna, h11, click, charset_normalizer, certifi, blinker, annotated-types, Werkzeug, typing-inspection, requests, pydantic-core, pyasn1-modules, proto-plus, Jinja2, httplib2, httpcore, gunicorn, grpcio, googleapis-common-protos, cffi, apscheduler, anyio, pydantic, httpx, grpcio-status, flask, cryptography, python-telegram-bot, google-auth, google-auth-httplib2, google-api-core, google-api-python-client, google-ai-generativelanguage, google-generativeai
Successfully installed Jinja2-3.1.6 MarkupSafe-3.0.3 Werkzeug-3.1.8 annotated-types-0.7.0 anyio-4.13.0 apscheduler-3.11.2 blinker-1.9.0 certifi-2026.2.25 cffi-2.0.0 charset_normalizer-3.4.7 click-8.3.2 cryptography-46.0.7 flask-3.0.2 google-ai-generativelanguage-0.6.15 google-api-core-2.30.3 google-api-python-client-2.194.0 google-auth-2.49.2 google-auth-httplib2-0.3.1 google-generativeai-0.8.6 googleapis-common-protos-1.74.0 grpcio-1.80.0 grpcio-status-1.71.2 gunicorn-21.2.0 h11-0.16.0 httpcore-1.0.9 httplib2-0.31.2 httpx-0.27.0 idna-3.11 itsdangerous-2.2.0 packaging-26.1 proto-plus-1.27.2 protobuf-5.29.6 pyasn1-0.6.3 pyasn1-modules-0.4.2 pycparser-3.0 pydantic-2.13.2 pydantic-core-2.46.2 pyparsing-3.3.2 python-telegram-bot-22.7 requests-2.33.1 sniffio-1.3.1 tqdm-4.67.3 typing-extensions-4.15.0 typing-inspection-0.4.2 tzlocal-5.3.1 uritemplate-4.2.0 urllib3-2.6.3
[notice] A new release of pip is available: 24.0 -> 26.0.1
[notice] To update, run: pip install --upgrade pip
==> Uploading build...
==> Uploaded in 3.0s. Compression took 3.9s
==> Build successful 🎉
==> Deploying...
https://github.com/google-gemini/deprecated-generative-ai-python/blob/main/README.md
  import google.generativeai as genai
/opt/render/project/src/app.py:1221: PTBUserWarning: If 'per_message=False', 'CallbackQueryHandler' will not be tracked for every message. Read this FAQ entry to learn more about the per_* settings: https://github.com/python-telegram-bot/python-telegram-bot/wiki/Frequently-Asked-Questions#what-do-the-per_-settings-in-conversationhandler-do.
  ptb_app.add_handler(ConversationHandler(
/opt/render/project/src/app.py:1229: PTBUserWarning: If 'per_message=False', 'CallbackQueryHandler' will not be tracked for every message. Read this FAQ entry to learn more about the per_* settings: https://github.com/python-telegram-bot/python-telegram-bot/wiki/Frequently-Asked-Questions#what-do-the-per_-settings-in-conversationhandler-do.
  ptb_app.add_handler(ConversationHandler(
/opt/render/project/src/app.py:1237: PTBUserWarning: If 'per_message=False', 'CallbackQueryHandler' will not be tracked for every message. Read this FAQ entry to learn more about the per_* settings: https://github.com/python-telegram-bot/python-telegram-bot/wiki/Frequently-Asked-Questions#what-do-the-per_-settings-in-conversationhandler-do.
  ptb_app.add_handler(ConversationHandler(
/opt/render/project/src/app.py:1245: PTBUserWarning: If 'per_message=False', 'CallbackQueryHandler' will not be tracked for every message. Read this FAQ entry to learn more about the per_* settings: https://github.com/python-telegram-bot/python-telegram-bot/wiki/Frequently-Asked-Questions#what-do-the-per_-settings-in-conversationhandler-do.
  ptb_app.add_handler(ConversationHandler(
/opt/render/project/src/app.py:1253: PTBUserWarning: If 'per_message=False', 'CallbackQueryHandler' will not be tracked for every message. Read this FAQ entry to learn more about the per_* settings: https://github.com/python-telegram-bot/python-telegram-bot/wiki/Frequently-Asked-Questions#what-do-the-per_-settings-in-conversationhandler-do.
  ptb_app.add_handler(ConversationHandler(
/opt/render/project/src/app.py:1264: PTBUserWarning: If 'per_message=False', 'CallbackQueryHandler' will not be tracked for every message. Read this FAQ entry to learn more about the per_* settings: https://github.com/python-telegram-bot/python-telegram-bot/wiki/Frequently-Asked-Questions#what-do-the-per_-settings-in-conversationhandler-do.
  ptb_app.add_handler(ConversationHandler(
/opt/render/project/src/app.py:1272: PTBUserWarning: If 'per_message=False', 'CallbackQueryHandler' will not be tracked for every message. Read this FAQ entry to learn more about the per_* settings: https://github.com/python-telegram-bot/python-telegram-bot/wiki/Frequently-Asked-Questions#what-do-the-per_-settings-in-conversationhandler-do.
  ptb_app.add_handler(ConversationHandler(
/opt/render/project/src/app.py:1280: PTBUserWarning: If 'per_message=False', 'CallbackQueryHandler' will not be tracked for every message. Read this FAQ entry to learn more about the per_* settings: https://github.com/python-telegram-bot/python-telegram-bot/wiki/Frequently-Asked-Questions#what-do-the-per_-settings-in-conversationhandler-do.
  ptb_app.add_handler(ConversationHandler(
2026-04-19 13:00:52,335 - httpx - INFO - HTTP Request: POST https://api.telegram.org/bot8648572662:AAEmzOSkG8r1UItoA59uoGdBEeAgToJ-Sps/getMe "HTTP/1.1 200 OK"
2026-04-19 13:00:52,496 - httpx - INFO - HTTP Request: POST https://api.telegram.org/bot8648572662:AAEmzOSkG8r1UItoA59uoGdBEeAgToJ-Sps/setWebhook "HTTP/1.1 200 OK"
2026-04-19 13:00:52,497 - app - INFO - Webhook set: https://adapprovalpilot-ai-sgdc.onrender.com/8648572662:AAEmzOSkG8r1UItoA59uoGdBEeAgToJ-Sps
[2026-04-19 13:00:52 +0000] [59] [INFO] Starting gunicorn 21.2.0
[2026-04-19 13:00:52 +0000] [59] [INFO] Listening at: http://0.0.0.0:10000 (59)
[2026-04-19 13:00:52 +0000] [59] [INFO] Using worker: gthread
[2026-04-19 13:00:52 +0000] [64] [INFO] Booting worker with pid: 64
127.0.0.1 - - [19/Apr/2026:13:00:52 +0000] "HEAD / HTTP/1.1" 200 0 "-" "Go-http-client/1.1"
==> Your service is live 🎉
==> 
==> ///////////////////////////////////////////////////////////
==> 
==> Available at your primary URL https://adapprovalpilot-ai-sgdc.onrender.com
==> 
==> ///////////////////////////////////////////////////////////
2026-04-19 13:01:33,701 - telegram.ext.Application - ERROR - No error handlers are registered, logging exception.
Traceback (most recent call last):
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/telegram/request/_baserequest.py", line 305, in _request_wrapper
    code, payload = await self.do_request(
                    ^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/telegram/request/_httpxrequest.py", line 279, in do_request
    res = await self._client.request(
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/httpx/_client.py", line 1574, in request
    return await self.send(request, auth=auth, follow_redirects=follow_redirects)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/httpx/_client.py", line 1661, in send
    response = await self._send_handling_auth(
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/httpx/_client.py", line 1689, in _send_handling_auth
    response = await self._send_handling_redirects(
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/httpx/_client.py", line 1726, in _send_handling_redirects
    response = await self._send_single_request(request)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/httpx/_client.py", line 1763, in _send_single_request
    response = await transport.handle_async_request(request)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/httpx/_transports/default.py", line 373, in handle_async_request
    resp = await self._pool.handle_async_request(req)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/httpcore/_async/connection_pool.py", line 256, in handle_async_request
    raise exc from None
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/httpcore/_async/connection_pool.py", line 229, in handle_async_request
    await self._close_connections(closing)
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/httpcore/_async/connection_pool.py", line 345, in _close_connections
    await connection.aclose()
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/httpcore/_async/connection.py", line 173, in aclose
    await self._connection.aclose()
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/httpcore/_async/http11.py", line 258, in aclose
    await self._network_stream.aclose()
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/httpcore/_backends/anyio.py", line 53, in aclose
    await self._stream.aclose()
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/anyio/streams/tls.py", line 236, in aclose
    await self.transport_stream.aclose()
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/anyio/_backends/_asyncio.py", line 1344, in aclose
    self._transport.close()
  File "/opt/render/project/python/Python-3.12.2/lib/python3.12/asyncio/selector_events.py", line 1210, in close
    super().close()
  File "/opt/render/project/python/Python-3.12.2/lib/python3.12/asyncio/selector_events.py", line 875, in close
    self._loop.call_soon(self._call_connection_lost, None)
  File "/opt/render/project/python/Python-3.12.2/lib/python3.12/asyncio/base_events.py", line 793, in call_soon
    self._check_closed()
  File "/opt/render/project/python/Python-3.12.2/lib/python3.12/asyncio/base_events.py", line 540, in _check_closed
    raise RuntimeError('Event loop is closed')
RuntimeError: Event loop is closed
The above exception was the direct cause of the following exception:
Traceback (most recent call last):
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/telegram/ext/_application.py", line 1315, in process_update
    await coroutine
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/telegram/ext/_handlers/basehandler.py", line 159, in handle_update
    return await self.callback(update, context)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/app.py", line 398, in start
    await update.message.reply_text(
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/telegram/_message.py", line 2106, in reply_text
    return await self.get_bot().send_message(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/telegram/ext/_extbot.py", line 3118, in send_message
    return await super().send_message(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/telegram/_bot.py", line 1123, in send_message
    return await self._send_message(
           ^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/telegram/ext/_extbot.py", line 630, in _send_message
    result = await super()._send_message(
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/telegram/_bot.py", line 820, in _send_message
    result = await self._post(
             ^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/telegram/_bot.py", line 704, in _post
    return await self._do_post(
           ^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/telegram/ext/_extbot.py", line 370, in _do_post
    return await super()._do_post(
           ^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/telegram/_bot.py", line 733, in _do_post
    result = await request.post(
             ^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/telegram/request/_baserequest.py", line 198, in post
    result = await self._request_wrapper(
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/telegram/request/_baserequest.py", line 317, in _request_wrapper
    raise NetworkError(f"Unknown error in HTTP implementation: {exc!r}") from exc
telegram.error.NetworkError: Unknown error in HTTP implementation: RuntimeError('Event loop is closed')
10.30.39.129 - - [19/Apr/2026:13:01:33 +0000] "POST /8648572662:AAEmzOSkG8r1UItoA59uoGdBEeAgToJ-Sps HTTP/1.1" 200 2 "-" "-"
2026-04-19 13:01:38,550 - httpx - INFO - HTTP Request: POST https://api.telegram.org/bot8648572662:AAEmzOSkG8r1UItoA59uoGdBEeAgToJ-Sps/sendMessage "HTTP/1.1 200 OK"
10.31.71.1 - - [19/Apr/2026:13:01:38 +0000] "POST /8648572662:AAEmzOSkG8r1UItoA59uoGdBEeAgToJ-Sps HTTP/1.1" 200 2 "-" "-"
2026-04-19 13:01:44,579 - telegram.ext.Application - ERROR - No error handlers are registered, logging exception.
Traceback (most recent call last):
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/telegram/request/_baserequest.py", line 305, in _request_wrapper
    code, payload = await self.do_request(
                    ^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/telegram/request/_httpxrequest.py", line 279, in do_request
    res = await self._client.request(
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/httpx/_client.py", line 1574, in request
    return await self.send(request, auth=auth, follow_redirects=follow_redirects)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/httpx/_client.py", line 1661, in send
    response = await self._send_handling_auth(
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/httpx/_client.py", line 1689, in _send_handling_auth
    response = await self._send_handling_redirects(
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/httpx/_client.py", line 1726, in _send_handling_redirects
    response = await self._send_single_request(request)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/httpx/_client.py", line 1763, in _send_single_request
    response = await transport.handle_async_request(request)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/httpx/_transports/default.py", line 373, in handle_async_request
    resp = await self._pool.handle_async_request(req)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/httpcore/_async/connection_pool.py", line 256, in handle_async_request
    raise exc from None
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/httpcore/_async/connection_pool.py", line 229, in handle_async_request
    await self._close_connections(closing)
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/httpcore/_async/connection_pool.py", line 345, in _close_connections
    await connection.aclose()
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/httpcore/_async/connection.py", line 173, in aclose
    await self._connection.aclose()
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/httpcore/_async/http11.py", line 258, in aclose
    await self._network_stream.aclose()
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/httpcore/_backends/anyio.py", line 53, in aclose
    await self._stream.aclose()
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/anyio/streams/tls.py", line 236, in aclose
    await self.transport_stream.aclose()
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/anyio/_backends/_asyncio.py", line 1344, in aclose
    self._transport.close()
  File "/opt/render/project/python/Python-3.12.2/lib/python3.12/asyncio/selector_events.py", line 1210, in close
    super().close()
  File "/opt/render/project/python/Python-3.12.2/lib/python3.12/asyncio/selector_events.py", line 875, in close
    self._loop.call_soon(self._call_connection_lost, None)
  File "/opt/render/project/python/Python-3.12.2/lib/python3.12/asyncio/base_events.py", line 793, in call_soon
    self._check_closed()
  File "/opt/render/project/python/Python-3.12.2/lib/python3.12/asyncio/base_events.py", line 540, in _check_closed
    raise RuntimeError('Event loop is closed')
RuntimeError: Event loop is closed
The above exception was the direct cause of the following exception:
Traceback (most recent call last):
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/telegram/ext/_application.py", line 1315, in process_update
    await coroutine
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/telegram/ext/_handlers/basehandler.py", line 159, in handle_update
    return await self.callback(update, context)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/app.py", line 398, in start
    await update.message.reply_text(
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/telegram/_message.py", line 2106, in reply_text
    return await self.get_bot().send_message(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/telegram/ext/_extbot.py", line 3118, in send_message
    return await super().send_message(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/telegram/_bot.py", line 1123, in send_message
    return await self._send_message(
           ^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/telegram/ext/_extbot.py", line 630, in _send_message
    result = await super()._send_message(
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/telegram/_bot.py", line 820, in _send_message
    result = await self._post(
             ^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/telegram/_bot.py", line 704, in _post
    return await self._do_post(
           ^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/telegram/ext/_extbot.py", line 370, in _do_post
    return await super()._do_post(
           ^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/telegram/_bot.py", line 733, in _do_post
    result = await request.post(
             ^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/telegram/request/_baserequest.py", line 198, in post
    result = await self._request_wrapper(
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/telegram/request/_baserequest.py", line 317, in _request_wrapper
    raise NetworkError(f"Unknown error in HTTP implementation: {exc!r}") from exc
telegram.error.NetworkError: Unknown error in HTTP implementation: RuntimeError('Event loop is closed')
10.19.183.242 - - [19/Apr/2026:13:01:44 +0000] "POST /8648572662:AAEmzOSkG8r1UItoA59uoGdBEeAgToJ-Sps HTTP/1.1" 200 2 "-" "-"
2026-04-19 13:01:55,921 - httpx - INFO - HTTP Request: POST https://api.telegram.org/bot8648572662:AAEmzOSkG8r1UItoA59uoGdBEeAgToJ-Sps/answerCallbackQuery "HTTP/1.1 200 OK"
2026-04-19 13:01:56,113 - httpx - INFO - HTTP Request: POST https://api.telegram.org/bot8648572662:AAEmzOSkG8r1UItoA59uoGdBEeAgToJ-Sps/editMessageText "HTTP/1.1 200 OK"
10.20.171.132 - - [19/Apr/2026:13:01:56 +0000] "POST /8648572662:AAEmzOSkG8r1UItoA59uoGdBEeAgToJ-Sps HTTP/1.1" 200 2 "-" "-"
