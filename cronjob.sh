#! /bin/bash

# ask whether to add or remove the cronjob
echo "Do you want to add or remove the cronjob?"
read -p "Enter 'add | a' or 'remove | r': " action
# resolve the full file path to run.py in the current directory
script="(cd "$(readlink -f .)" || exit 1; .venv/bin/python "$(readlink -f run.py)")"
# if the user wants to add the cronjob
if [ "$action" == "add" ] || [ "$action" == "a" ]; then
    # ask for the time to run the script
    # add the cronjob
    (crontab -l; echo "0 * * * * $script") | crontab -
    echo "Cronjob added successfully! Running the script every hour."
# if the user wants to remove the cronjob
elif [ "$action" == "remove" ] || [ "$action" == "r" ]; then
    # remove the cronjob
    crontab -l | grep -v "$script" | crontab -
    echo "Cronjob removed successfully!"
# if the user enters an invalid action
else
    echo "Invalid action!"
fi
