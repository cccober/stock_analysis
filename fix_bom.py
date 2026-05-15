file_path = 'src/api/main.py'

with open(file_path, 'rb') as f:
    content = f.read()

# Remove all BOMs from the beginning
while content.startswith(b'\xef\xbb\xbf'):
    content = content[3:]

with open(file_path, 'wb') as f:
    f.write(content)

print("All BOMs removed successfully")
