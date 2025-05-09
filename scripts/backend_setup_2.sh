poetry install --no-root --with dev 
poetry run pip install --upgrade "huggingface_hub[cli]"

# Manual login on the terminal
# poetry run huggingface-cli login

# Log in using environments/backend/.env
set -a
source environments/backend/.env
set +a
poetry run huggingface-cli login --token "$HF_TOKEN"