#!/bin/bash

# Loop through all .m4a files in the current directory
for file in data/*.m4a; do
    # Extract the filename without the extension
    filename="${file%.m4a}"
    
    # Convert the .m4a file to .wav
    ffmpeg -i "$file" "${filename}.wav" -y
    
    # Optionally, you can remove the original .m4a file after conversion
    # rm "$file"
done

echo "Conversion completed!"
