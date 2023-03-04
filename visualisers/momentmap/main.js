const sortOptions = [
  { value: "date", label: "Date" },
  { value: "likes", label: "Likes" },
  { value: "views", label: "Views" },
  { value: "comments", label: "Comments" },
];

function sortRows(option, main) {
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
  }
}

Promise.all([
  d3.csv("data/playback_data.csv"),
  d3.csv("data/youtube_report.csv"),
]).then(([playbackData, youtubeReport]) => {
  const groups = Array.from(d3.group(playbackData, (d) => d["id"])).map((d) => {
    return [d[0], d[1], youtubeReport.filter((e) => e["id"] === d[0])[0]];
  });
  const main = d3.select("#main");
  const body = d3.select("body");
  let showTitles = d3.select("#show-titles");

  const sortMenu = d3
    .select("#header-container")
    .append("div")
    .attr("id", "sort-menu")
    .append("label")
    .text("Sort by: ")
    .append("select")
    .on("change", function () {
      const selectedOption = d3.select(this).property("value");
      sortRows(selectedOption, main);
    });

  sortMenu
    .selectAll("option")
    .data(sortOptions)
    .enter()
    .append("option")
    .attr("value", (d) => d.value)
    .text((d) => d.label);

  const rows = main
    .selectAll("div")
    .data(groups)
    .join("div")
    .attr("class", "row");

  // ROW
  // |__VIDEO-CONTAINER
  // |__STRIP-CONTAINER
  //    |__ TITLE-WRAPPER
  //    |__ FRAME-CONTAINER
  //        |__ FRAME
  //            |__ IMAGE

  const videoContainer = rows.append("div").attr("class", "video-container");

  videoContainer.on("click", function (e, d) {
    if (!e.target.classList.contains("video-container")) return;
    d3.select(this).classed("active", false);
    d3.select(this).selectAll("*").remove();
  });

  body.on("click", function (e, d) {
    if (e.target.localName !== "body") return;
    d3.selectAll(".video-container").classed("active", false);
    d3.selectAll(".video-container").selectAll("*").remove();
  });

  const stripContainer = rows.append("div").attr("class", "strip-container");

  const titleBox = stripContainer.append("div").attr("class", "title-box");

  const titles = titleBox
    .append("p")
    .attr("class", "video-title")
    .text((d) => {
      const id = d[0];
      const title = youtubeReport.find((d) => d["id"] === id)["title"];
      return title;
    });

  const frameBox = stripContainer.append("div").attr("class", "frame-box");

  const frames = frameBox
    .selectAll("div:not(.title-box)")
    .data((d) => d[1])
    .join("div")
    .attr("class", "frame")
    //.style("height", (d) => `${d.score * 100}%`)
    .style("margin-top", "auto");

  const images = frames
    .append("img")
    .attr("src", (d) => `img/${d.id}_${d.segment}.jpg`)
    .style("opacity", (d) => d.score);

  frames
    .on("mouseover", function (d) {
      d3.select(this).classed("frame-fit", true);
      d3.select(this).select("img").style("opacity", 1);
    })
    .on("mouseout", function (d) {
      d3.select(this).classed("frame-fit", false);
      d3.select(this)
        .select("img")
        .style("opacity", (d) => d.score);
    });

  main
    .on("mouseover", function (d) {
      frames.style("transition", "none");
    })
    .on("mouseout", function (d) {
      frames.style("transition", "cubic-bezier(0.075, 0.82, 0.165, 1) 0.5s");
      frames.classed("frame-fit", false);
    });

  showTitles.on("click", function (_d) {
    if (showTitles.html().includes("chevron_right")) {
      showTitles.html(
        "Hide Titles <span class='material-symbols-outlined'>chevron_left</span>"
      );
    } else {
      showTitles.html(
        "Show Titles <span class='material-symbols-outlined'>chevron_right</span>"
      );
    }
    titleBox.classed("active", !titleBox.classed("active"));
  });

  frames.on("click", function (e, d) {
    const videoContainer = d3
      .select(this.parentNode.parentNode.parentNode)
      .select(".video-container");

    if (videoContainer.classed("active")) {
      if (ytPlayer) {
        ytPlayer.seekTo(Math.floor(d.start_sec));
      }
      (d) => `${(1 - d.score) * 100}%`;
      return;
    } else {
      d3.selectAll(".video-container").classed("active", false);
      d3.selectAll(".video-container").selectAll("*").remove();
      videoContainer.classed("active", true);
      const playerContainer = videoContainer
        .append("div")
        .attr("class", "player-container");
      const player = playerContainer.append("div").attr("id", "player");
      const info = playerContainer.append("div").attr("id", "info");
      const index = this.parentNode.parentNode.parentNode.__data__[0];
      const vidInfo = youtubeReport.find((row) => row["id"] === index);

      info.append("h2").text(vidInfo["title"]);

      info
        .append("p")
        .text(vidInfo["channel"] + ", " + formatDate(vidInfo["date"]));

      const infoRow = info.append("div").attr("id", "info-row");

      infoRow
        .append("div")
        .html(
          `<span class='material-symbols-outlined'>visibility</span>${Number(
            vidInfo["views"]
          ).toLocaleString()}`
        );
      infoRow
        .append("div")
        .html(
          `<span class='material-symbols-outlined'>thumb_up</span>${
            Number(vidInfo["likes"]).toLocaleString() || 0
          }`
        );
      infoRow
        .append("div")
        .html(
          `<span class='material-symbols-outlined'>comment</span>${
            Number(vidInfo["comments"]).toLocaleString() || 0
          }`
        );
      info.append("p").text(vidInfo["description"]);

      ytPlayer = new YT.Player("player", {
        height: "360px",
        width: "640px",
        videoId: d.id,
        playerVars: {
          start: Math.floor(d.start_sec),
          autoplay: 1,
          controls: 1,
          loop: 1,
          modestbranding: 1,
          showInfo: 0,
          fs: 0,
          iv_load_policy: 3,
          rel: 0,
        },
        events: {
          onReady: onPlayerReady,
        },
      });

      function onPlayerReady(event) {
        event.target.playVideo();
      }
    }
  });
});
