function formatDate(dateString) {
    const date = new Date(dateString);
    const months = [
      "January", "February", "March", "April", "May", "June", "July",
      "August", "September", "October", "November", "December",
    ];
    let outString = "";
    const month = months[date.getUTCMonth()];
    const day = date.getUTCDate();
    const year = date.getUTCFullYear();
    const hour = date.getUTCHours();
    const minute = date.getUTCMinutes();
  
    outString += month + " " + day;
  
    switch (day % 10) {
      case 1:
        outString += "st";
        break;
      case 2:
        outString += "nd";
        break;
      case 3:
        outString += "rd";
        break;
      default:
        outString += "th";
        break;
    }
  
    outString += " " + year + " at ";
    outString += hour + ":";
    outString += (minute < 10 ? "0" : "") + minute;
  
    return outString;
  }