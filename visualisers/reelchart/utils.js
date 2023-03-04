function formatDate(dateString) {
  const date = new Date(dateString);
  const months = ["January", "February", "March", "April", "May", "June", 
  "July", "August", "September", "October", "November", "December"];
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
  outString += (minute < 10 ? "0" : "") + minute + " UTC";

  return outString;
}

const formatTimeString = (time) => {
  const hours = Math.floor(time / 3600);
  const minutes = Math.floor((time % 3600) / 60);
  const seconds = Math.floor(time % 60);
  return (
    (hours ? hours + ":" : "") +
    (minutes < 10 ? "0" : "") +
    minutes +
    ":" +
    (seconds < 10 ? "0" : "") +
    seconds
  );
};

const map2range = (x, in_min, in_max, out_min, out_max) => {
  return ((x - in_min) * (out_max - out_min)) / (in_max - in_min) + out_min;
};

const sortOptions = [
  { value: "date", label: "Date" },
  { value: "likes", label: "Likes" },
  { value: "views", label: "Views" },
  { value: "comments", label: "Comments" },
  { value: "mentions", label: "Mentions" },
];

function sortRows(option, main, pb_data, selectedWords) {
  switch (option) {
    case "date":
      main
        .selectAll(".row")
        .sort((a, b) => d3.descending(new Date(a[2].date), new Date(b[2].date)));
      break;
    case "likes":
      main
        .selectAll(".row")
        .sort((a, b) => d3.descending(+a[2].likes, +b[2].likes));
      break;
    case "views":
      main
        .selectAll(".row")
        .sort((a, b) => d3.descending(+a[2].views, +b[2].views));
      break;
    case "comments":
      main
        .selectAll(".row")
        .sort((a, b) => d3.descending(+a[2].comments || 0, +b[2].comments || 0));
      break;
    case "mentions":
      main.selectAll(".row").sort((a, b) => {
        const aMentions = pb_data.filter(
          (d) => d.id === a[0] && selectedWords.includes(d.word)
        ).length;
        const bMentions = pb_data.filter(
          (d) => d.id === b[0] && selectedWords.includes(d.word)
        ).length;
        return d3.descending(aMentions, bMentions);
      });
      break;
  }
}
