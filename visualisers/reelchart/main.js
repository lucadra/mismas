selectedWords = [];

function showResults(
  results,
  searchResults,
  searchInput,
  selectedWords,
  searchButton,
  body
) {
  const searchResult = searchResults
    .selectAll(".search-result")
    .data(results, (d) => d.word);
  console.log("outer", selectedWords);

  searchResult
    .enter()
    .append("div")
    .attr("class", "search-result")
    .text((d) => d.word)
    .on("click", function (_e, d) {
      let selectedWordsCopy = selectedWords.slice();
      searchInput.property("value", d.word);
      searchResults.style("display", "none");
      if (!selectedWordsCopy.includes(d.word)) {
        selectedWords.push(d.word);
      }
      searchButton.on("click")(selectedWords);
      d3.selectAll("#dark-overlay").remove();
    });

  if (results.length > 0) {
    searchResults.style("display", "block");
    if (d3.selectAll("#dark-overlay").empty()) {
      body.append("div").attr("id", "dark-overlay");
    }
  } else {
    searchResults.style("display", "none");
    d3.selectAll("#dark-overlay").remove();
  }

  searchResult.exit().remove();
}

function handleInput(
  e,
  wordCounts,
  searchResults,
  searchInput,
  selectedWords,
  searchButton,
  body
) {
  let inputValue = e.target.value.trim();

  if (inputValue === "") {
    searchResults.style("display", "none");
  } else {
    let filteredCounts = wordCounts
      .filter((d) => d.word.startsWith(inputValue.toLowerCase()))
      .sort((a, b) => b.count - a.count)
      .slice(0, 5);

    showResults(
      filteredCounts,
      searchResults,
      searchInput,
      selectedWords,
      searchButton,
      body
    );
  }
}

function updateSelectedWords(selectedWordsDiv, _selectedWords, searchButton) {
  selectedWordsDiv
    .selectAll("div")
    .data(_selectedWords)
    .enter()
    .append("div")
    .attr("class", "selected-word")
    .append("p")
    .text((d) => d)
    .append("span")
    .attr("class", "material-symbols-outlined")
    .html("close")
    .on("click", function (_e, d) {
      selectedWords = _selectedWords.filter((word) => word !== d);
      d3.select(this.parentNode).remove();
      searchButton.on("click")(selectedWords);
    });
  return selectedWords;
}

function setFramesOpacity(selectedWords, speechData) {
  if (selectedWords.length > 0) {
    d3.selectAll(".frame").each(function (d, _i) {
      let index = d;
      let video_id = this.parentNode.parentNode.parentNode.__data__[0];

      const shouldBeVisible =
        speechData.filter(
          (d) =>
            selectedWords.includes(d["word"]) &&
            d["id"] === video_id &&
            +d["segment"] === index
        ).length > 0;

      d3.select(this).classed("hidden-frame", !shouldBeVisible);
    });
  } else {
    console.log("no words selected");
    d3.selectAll(".frame").classed("hidden-frame", false);
  }
}

///////////////////////////////////////////////////////////////////////////////
///////////////////////////////////////////////////////////////////////////////
///////////////////////////////////////////////////////////////////////////////

Promise.all([
  d3.csv("data/speech_data.csv"),
  d3.csv("data/youtube_report.csv"),
]).then(([speechData, youtubeReport]) => {
  const main = d3.select("#main");
  const body = d3.select("body");

  const groups = Array.from(d3.group(speechData, (d) => d["id"])).map((d) => {
    return [d[0], d[1], youtubeReport.filter((e) => e["id"] === d[0])[0]];
  });
  const words = [...new Set(speechData.map((d) => d["word"]))];

  const wordCounts = words
    .map((word) => {
      const count = speechData.filter((d) => d["word"] === word).length;
      return { word: word, count: count };
    })
    .sort((a, b) => b["count"] - a["count"]);

  let selectedWordsDiv = d3.select("#selected-words");
  let searchInput = d3.select("#search-input");
  let searchButton = d3.select("#search-button");
  let searchResults = d3.select("#search-results");
  let showTitles = d3.select("#show-titles");

  searchInput.on("input", (e) =>
    handleInput(
      e,
      wordCounts,
      searchResults,
      searchInput,
      selectedWords,
      searchButton,
      body
    )
  );

  searchButton.on("click", function (selectedWords) {
    if (!searchInput.property("value").trim() === "") {
      selectedWords.push(searchInput.property("value").trim());
    }
    setFramesOpacity(selectedWords, speechData);
    selectedWordsDiv.selectAll("*").remove();
    selectedWords = updateSelectedWords(
      selectedWordsDiv,
      selectedWords,
      searchButton
    );
    searchInput.property("value", "");
  });

  const sortMenu = d3
    .select("#header")
    .append("div")
    .attr("id", "sort-menu")
    .append("label")
    .text("Sort by: ")
    .append("select")
    .on("change", function () {
      const selectedOption = d3.select(this).property("value");
      sortRows(selectedOption, main, speechData, selectedWords);
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

  videoContainer.on("click", function (e, _d) {
    if (!e.target.classList.contains("video-container")) return;
    d3.select(this).classed("active", false);
    d3.select(this).selectAll("*").remove();
  });

  body.on("click", function (e, _d) {
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
    .selectAll("div")
    .data((_d) => Array.from({ length: 20 }, (_, i) => i))
    .join("div")
    .attr("class", "frame");

  const images = frames.append("img").attr("src", function (_d, i) {
    let video_id = this.parentNode.parentNode.parentNode.parentNode.__data__[0];
    return `img/${video_id}_${i}.jpg`;
  });

  frames
    .on("mouseover", function (_d) {
      d3.select(this).classed("frame-fit", true);
      d3.select(this).select("img").style("opacity", 1);
    })
    .on("mouseout", function (_d) {
      d3.select(this).classed("frame-fit", false);
      d3.select(this).select("img");
    });

  main
    .on("mouseover", function (_d) {
      frames.style("transition", "none");
    })
    .on("mouseout", function (_d) {
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

  frames.on("click", function (_e, d) {
    if (d3.select(this).classed("hidden-frame")) return;

    const videoContainer = d3
      .select(this.parentNode.parentNode.parentNode)
      .select(".video-container");

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

    let earliestTimestamp = 0;

    if (selectedWords.length > 0) {
      const segmentWords = speechData
        .filter((row) => row["id"] === index && +row["segment"] === d)
        .filter((row) => selectedWords.includes(row["word"]));
      earliestTimestamp =
        segmentWords[0] === undefined ? 0 : segmentWords[0]["start_sec"];

      info.append("h3").text("Mentions of searched words:");
      const wordInfo = info.append("div").attr("id", "word-info");

      segmentWords.forEach((row) => {
        const word = row["word"];
        const timestamp = row["start_sec"];
        const wordWrapper = wordInfo
          .append("div")
          .attr("class", "word-wrapper");
        wordWrapper.append("p").text(word);
        wordWrapper.append("p").text(formatTimeString(timestamp));
        wordWrapper.on("click", function (_e, _d) {
          ytPlayer.seekTo(Math.floor(timestamp));
        });
      });
    }

    info.append("p").text(vidInfo["description"]);
    ytPlayer = new YT.Player("player", {
      height: "360px",
      width: "640px",
      videoId: index,
      playerVars: {
        start: Math.floor(earliestTimestamp),
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
  });
});
