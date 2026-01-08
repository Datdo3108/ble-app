import subprocess
import time
import keyboard

# Path to the JLinkRTTViewer executable
jlink_rtt_viewer_path = "C:/Program Files/SEGGER/JLink_V798i/JLinkRTTViewer.exe"  # Adjust the path

# Launch the JLinkRTTViewer
process = subprocess.Popen([jlink_rtt_viewer_path])
time_0 = time.time()

# Give the viewer some time to open
time.sleep(1)

# Simulate pressing "Enter" to connect (assuming Enter works to initiate)
keyboard.send("enter")

# Simulate pressing F5 to start logging (if F5 starts logging)
keyboard.send("f5")

# Give some time for the file save dialog to appear
time.sleep(0.5)

# Step 4: Generate a unique filename using a timestamp
timestamp = time.strftime("%Y%m%d_%H%M%S")  # Example: 20240925_153012
file_path = f"my_log_{timestamp}.txt"       # File name with timestamp

# Type the unique filename
keyboard.write(file_path)      

# Press Enter to confirm saving the log with the given filename
keyboard.send("enter")


# while(time.time() - time_0 <= 14):
#     pass
# keyboard.send("enter")

# Wait for the user to close the viewer
process.wait()
