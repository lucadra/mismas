const getImgPath = (d) => {
  let timestamp = Number(d.end_time).toFixed(3);
  return `img/${d.object_name}_${d.object_id}_[${timestamp}].jpg`;
};

const secondsToTime = (seconds) => {
  let hours = Math.floor(seconds / 3600);
  seconds = seconds % 3600;
  let minutes = Math.floor(seconds / 60);
  seconds = seconds % 60;

  if (hours > 0) {
    return `${hours}h ${minutes}m ${seconds}s`;
  } else if (minutes > 0) {
    return `${minutes}m ${seconds}s`;
  } else {
    return `${seconds}s`;
  }
};

const getTooltipString = (d) => {
  return `This ${d.object_name} is continuously visible for ${secondsToTime(
    Math.round(d.duration)
  )}`;
};

function appendGroupImages(d, collection) {
  let minDuration = d3.min(d.objectsData, (d) => +d.duration);
  let maxDuration = d3.max(d.objectsData, (d) => +d.duration);

  const height = d3
    .select(collection.node().parentNode.parentNode)
    .node()
    .getBoundingClientRect().height;

  d.objectsData.forEach((d) => {
    let imageHeight = map2range(
      +d.duration,
      minDuration,
      maxDuration,
      10,
      height
    );

    let container = collection
      .append("div")
      .attr("class", "container")
      .append("a")
      .attr("href", getImgPath(d));

    let images = container
      .append("img")
      .attr("src", getImgPath(d))
      .attr("height", imageHeight)
      .attr("alt", `${d.object_name}_${d.object_id}`);

    handleTooltip(images, d, imageHeight);
  });
}

function handleTooltip(images, d, imageHeight) {
  images
    .on("mouseover", function (e) {
      let parentHeight =
        this.parentNode.parentNode.parentNode.getBoundingClientRect().height;
      d3.select(this).attr("height", `${parentHeight}px`);

      d3.select("body")
        .append("div")
        .attr("class", "tooltip")
        .style("top", e.pageY - 10 + "px")
        .style("left", e.pageX + 10 + "px")
        .text(getTooltipString(d));
    })
    .on("mouseout", function () {
      d3.select("body").selectAll(".tooltip").remove();
      d3.select(this).attr("height", imageHeight);
    });
}

function handleDragDrop(collection) {
  collection.on("mousedown", function (e) {
    collection.style("cursor", "grabbing");
    e.preventDefault();
    let startX = e.clientX;
    let scrollLeft = this.scrollLeft;
    let self = this;

    d3.select("body")
      .on("mousemove", function (e) {
        self.scrollLeft = scrollLeft - (e.clientX - startX);
      })
      .on("mouseup", function () {
        d3.select("body").on("mousemove", null);
        collection.style("cursor", "default");
      });
  });
}

///////////////////////////////////////////////////////////////////////////////
//---------------------------------- MAIN -----------------------------------//
///////////////////////////////////////////////////////////////////////////////

d3.csv("data/object_data.csv", (d) => d).then(function (data) {
  const root = d3.select("#showcase");
  const spinner = d3.select("#spinner");

  let groups = d3
    .groups(data, (d) => d.object_name)
    .map((d) => {
      return {
        objectsName: d[0],
        objectsData: d[1].sort((a, b) => b.duration - a.duration).slice(0, 100),
        objectsCount: d[1].length,
        totalDuration: d3.sum(d[1], (d) => d.duration),
      };
    })
    .sort((a, b) => b.totalDuration - a.totalDuration);

  groups.forEach((d) => {
    let group = root.append("div").attr("class", "group");

    let text = group.append("div").attr("class", "text");
    let landscapeView = group.append("div").attr("class", "landscape-view");

    text.append("h2").text(d.objectsName);
    let chev = text
      .append("p")
      .html('<span class="material-symbols-outlined">chevron_right</span>')
      .style("cursor", "pointer");

    appendObjectsLandscape(d, group);
    spinner.style("display", "none");

    let scrollBox = group
      .append("div")
      .attr("class", "scrollBox")
      .classed("hidden", true);
    let collection = scrollBox.append("div").attr("class", "images");

    handleDragDrop(collection);
    appendGroupImages(d, collection);

    chev.on("click", function (e, d) {
      if (group.classed("active")) {
        group.classed("active", false);
        landscapeView.classed("hidden", false);
        scrollBox.classed("hidden", true);
        chev.html(
          '<span class="material-symbols-outlined">chevron_right</span>'
        );
      } else {
        group.classed("active", true);
        landscapeView.classed("hidden", true);
        scrollBox.classed("hidden", false);
        chev.html(
          '<span class="material-symbols-outlined">chevron_left</span>'
        );
      }
    });
  });
});

function appendObjectsLandscape(d, self) {
  const data = d.objectsData;

  const min_duration = d3.min(d.objectsData, (d) => +d.duration);
  const max_duration = d3.max(d.objectsData, (d) => +d.duration);

  const rectangles = data
    .map((d) => [
      map2range(+d.duration, min_duration, max_duration, 100, 10000),
      d.aspect_ratio,
      getImgPath(d),
    ])
    .sort((a, b) => b[0] - a[0])
    .slice(0, 100);

  const row = self.node();

  const width = d3
    .select(row)
    .select(".landscape-view")
    .node()
    .getBoundingClientRect().width;

  const textBox = d3.select(row).select(".text").node().getBoundingClientRect();
  const height = width - textBox.height;

  const arrangement = arrange(rectangles, width, height, row);

  let svg = d3
    .select(row)
    .select(".landscape-view")
    .append("svg")
    .attr("width", width)
    .attr("height", height)
    .attr("viewBox", `0 0 ${width} ${height}`);

  let g = svg.append("g");

  g.selectAll("image")
    .data(arrangement.rects)
    .enter()
    .append("image")
    .attr("x", (d) => d[0][0].p[0])
    .attr("y", (d) => d[0][0].p[1])
    .attr("width", (d) => d[0][1].p[0] - d[0][0].p[0])
    .attr("height", (d) => d[0][3].p[1] - d[0][0].p[1])
    .attr("xlink:href", (d) => d[1]);

  // fit g to svg
  const bbox = g.node().getBBox();
  const padding = 16;
  const scale = Math.min(
    (width - padding) / bbox.width,
    (height - padding) / bbox.height
  );
  const x = -bbox.x * scale + (width - bbox.width * scale) / 2;
  const y = -bbox.y * scale + (height - bbox.height * scale) / 2;

  g.attr("transform", `translate(${x},${y}) scale(${scale})`);

  //make svg zoomable and draggable, clip to the viewport
  // const zoom = d3.zoom().scaleExtent([0.1, 10]).on("zoom", zoomed);

  // const drag = d3
  //   .drag()
  //   .on("start", dragstarted)
  //   .on("drag", dragged)
  //   .on("end", dragended);

  // g.call(zoom);
  // g.call(drag);

  // function zoomed(event) {
  //   g.attr("transform", event.transform);
  // }

  // function dragstarted(event) {
  //   d3.select(this).raise().classed("active", true);
  // }

  // function dragged(event) {
  //   d3.select(this).attr("cx", event.x).attr("cy", event.y);
  // }

  // function dragended(event) {
  //   d3.select(this).classed("active", false);
  // }
}
