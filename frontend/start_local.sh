# #!/bin/bash

# # npm install express
# # npm install -D @types/express
# # npm install concurrently

# chmod -R 777 ./public/transcriptsts

# # Install dependencies if needed
# if [ ! -d "node_modules" ]; then
#     echo "Installing dependencies..."
#     npm install --legacy-peer-deps
# else
#     echo "Dependencies already installed."
# fi

# # Start the application
# echo "Starting the application..."
# npm run start

# # Activate local server:
# npm install
# pnpm run dev -- --host 0.0.0.0

#!/bin/bash

# Create transcripts directory if it doesn't exist
mkdir -p ./public/transcripts

# Set permissions for the transcripts directory
chmod -R 777 ./public/transcripts

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    npm install --legacy-peer-deps
else
    echo "Dependencies already installed."
fi

# Start the application
echo "Starting the application..."
npm run start