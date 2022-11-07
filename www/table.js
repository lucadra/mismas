function setTablev2(data) {
    dataMaster = data;
    dataView = data;

    tableWrapper = d3.select("#project-wrapper")
        .append("div")
        .attr("id", "table-wrapper")

    table = tableWrapper.append("table")
        .attr("id", "table")
        .attr("class", "table sortable");

    headerRow = table.append("thead")
        .append("tr")

    headers = headerRow.selectAll("th")
        .data(Object.keys(dataView[0]))
        .enter()
        .append("th")
        .attr("class", (d) => d)
        .text((d) => d)

    tableBody = table.append("tbody")

    rows = tableBody.selectAll("tr")
        .data(dataView)
        .enter()
        .append("tr")

    cells = rows.selectAll("td")
        .data((d) => Object.values(d))
        .enter()
        .append("td")
        .attr("class", (d, i) => Object.keys(dataView[0])[i])
        .append("span")
        .text((d) => d)

    headers.on("click", function () {
        const table = document.querySelector("#table");
        const headerIndex = Array.prototype.indexOf.call(
            this.parentNode.children,
            this
        );
        const currentIsAscending = this.classList.contains("th-sort-asc");

        sortTableByColumn(table, headerIndex, !currentIsAscending);
    })

    headers.on("mouseover", function (e, d) {
        console.log(d)
        tooltip = d3.select("body")
            .append("div")
            .attr("id", "tooltip")
            .style("position", "absolute")
            .style("left", e.pageX + 10 + "px")
            .style("top", e.pageY - 25 + "px")
            .selectAll("div")
            .data(dataView.map((row) => row[d]))
            .enter()
            .append("div")
            .attr("class", "tooltip-item")
            .text((d) => d)

    })
        .on("mouseout", function (e, d) {
            //if mouse leaves the header, remove the tooltip unless the user is hovering over the tooltip
            if (e.relatedTarget != document.getElementById("tooltip")) {
                d3.selectAll("#tooltip").remove();
            }
        })

    //append uniqque values in column to tooltip
    tableBody.on("mouseover", function (e, d) {
        d3.selectAll("#tooltip").remove();
    })

}


function setTable(tmp_report) {
    d3.select("#project-wrapper")
        .append("div")
        .attr("id", "table-wrapper")
        .append("table")
        .attr("id", "table")
        .attr("class", "table sortable");

    d3.select("#table")
        .append("thead")
        .append("tr")
        .selectAll("th")
        .data(Object.keys(tmp_report[0]))
        .enter()
        .append("th")
        .attr("class", (d) => d)
        .on("click", function () {
            const table = document.querySelector("#table");
            const headerIndex = Array.prototype.indexOf.call(
                this.parentNode.children,
                this
            );
            const currentIsAscending = this.classList.contains("th-sort-asc");

            sortTableByColumn(table, headerIndex, !currentIsAscending);
        })
        .text((d) => d)
        .on("mouseover", function (e, d) {
            d3.select(this).style("cursor", "pointer");

            if (d3.selectAll(".tooltip").size() == 0) {
                tooltip = d3.select("body")
                    .append("div")
                    .attr("class", "tooltip")
                    .style("position", "absolute")
                    .style("top", e.pageY - 10 + "px")
                    .style("left", e.pageX + 10 + "px")

                //if col contains numbers, set filter by range


                tooltip.selectAll("div")
                    .data(
                        Array.from(new Set(report.map((d) => d[d3.select(this).text()])))
                    )
                    .enter()
                    .append("div")
                    .attr("class", "tooltip-item")
                    .on("click", function (e, d) {
                        tmp_report = report.filter((r) => r[d3.select(this).className] == d);
                    })
            }
        })
        .on("mouseout", function (e, d) {
            d3.select(this).style("cursor", "default");

            var elem = document.elementFromPoint(e.pageX + 10, e.pageY - 10);

            if (elem.className != "tooltip") {
                d3.selectAll(".tooltip").remove();
            }
        });

    d3.select("#table")
        .append("tbody")
        .selectAll("tr")
        .data(tmp_report)
        .enter()
        .append("tr")
        .selectAll("td")
        .data((d) => Object.values(d))
        .enter()
        .append("td")
        .attr("class", (d, i) => Object.keys(tmp_report[0])[i])
        .append("span")
        .text((d) => d)

    d3.select("#table")
        .select("tbody")
        .on("click", function (e, d) {
            var elem = document.elementFromPoint(e.pageX, e.pageY);
            if (elem.className == "select") {
                d3.select(elem).remove();
            } else {
                d3.select(this)
                    .append("div")
                    .attr("class", "select")
                    .style("position", "absolute")
                    .style("top", e.pageY - 10 + "px")
                    .style("left", e.pageX + 10 + "px")
            }
            d3.selectAll(".tooltip").remove();
        })

    d3.select("thead")
        .select("tr")
        .insert("th", ":first-child")
        .attr("class", "checkbox")
        .append("input")
        .attr("type", "checkbox")
        .attr("id", "select-all")
        .on("click", function () {
            selectAll(this);
        });

    d3.select("tbody")
        .selectAll("tr")
        .insert("td", ":first-child")
        .attr("class", "checkbox")
        .append("input")
        .attr("type", "checkbox")
        .attr("class", "select")
        .on("click", function () {
            select(this);
        });

    d3.select("#project-wrapper").append("div").attr("id", "button-wrapper");

    d3.select("#button-wrapper")
        .append("button")
        .attr("id", "download")
        .attr("class", "btn btn-primary")
        .attr("disabled", true)
        .text("Download")
        .on("click", function () {
            selected = getSelected();
            console.log(selected);
        });
}


function selectAll(checkbox) {
    if (checkbox.checked) {
        d3.selectAll(".select").property("checked", true);
    } else {
        d3.selectAll(".select").property("checked", false);
    }

    updateButtons();
}


function select(checkbox) {
    if (checkbox.checked) {
        d3.select(checkbox).property("checked", true);
    } else {
        d3.select(checkbox).property("checked", false);
    }

    updateButtons();
}


function updateButtons() {
    if (d3.selectAll(".select:checked").size() > 0) {
        d3.select("#download").attr("disabled", null);
    } else {
        d3.select("#download").attr("disabled", true);
    }
}


function getSelected() {
    selected = [];
    d3.selectAll(".select:checked").each(function (d, i) {
        selected.push(d3.select(this.parentNode.parentNode).datum());
    });

    return selected;
}


function sortTableByColumn(table, column, asc = True) {
    const dirModifier = asc ? 1 : -1;
    const tBody = table.tBodies[0];
    const rows = Array.from(tBody.querySelectorAll("tr"));

    // Sort each row
    const sortedRows = rows.sort((a, b) => {
        const aColText = a
            .querySelector(`td:nth-child(${column + 1})`)
            .textContent.trim();
        const bColText = b
            .querySelector(`td:nth-child(${column + 1})`)
            .textContent.trim();
        //check if aColText and bColText are numbers
        if (aColText.match(/^-?\d+$/) && bColText.match(/^-?\d+$/)) {
            return parseFloat(aColText) > parseFloat(bColText)
                ? 1 * dirModifier
                : -1 * dirModifier;
        } else {
            return aColText > bColText ? 1 * dirModifier : -1 * dirModifier;
        }
    });

    // Remove all existing TRs from the table
    while (tBody.firstChild) {
        tBody.removeChild(tBody.firstChild);
    }

    // Re-add the newly sorted rows
    tBody.append(...sortedRows);

    // Remember how the column is currently sorted
    table
        .querySelectorAll("th")
        .forEach((th) => th.classList.remove("th-sort-asc", "th-sort-desc"));
    table
        .querySelector(`th:nth-child(${column + 1})`)
        .classList.toggle("th-sort-asc", asc);
    table
        .querySelector(`th:nth-child(${column + 1})`)
        .classList.toggle("th-sort-desc", !asc);
}

function filterTableByKey(table, column, key) {
    const tBody = table.tBodies[0];
    const rows = Array.from(tBody.querySelectorAll("tr"));

    // Filter each row
    const filteredRows = rows.filter((row) => {
        const rowText = row
            .querySelector(`td:nth-child(${column + 1})`)
            .textContent.trim();
        return rowText.match(key);
    });

    // Remove all existing TRs from the table
    while (tBody.firstChild) {
        tBody.removeChild(tBody.firstChild);
    }

    // Re-add the newly filtered rows
    tBody.append(...filteredRows);
}

function filterByRange(table, column, min = 0, max = Number.MAX_SAFE_INTEGER) {
    const tBody = table.tBodies[0];
    const rows = Array.from(tBody.querySelectorAll("tr"));

    // Filter each row
    const filteredRows = rows.filter((row) => {
        const rowText = row
            .querySelector(`td:nth-child(${column + 1})`)
            .textContent.trim();
        return parseFloat(rowText) >= min && parseFloat(rowText) <= max;
    });

    // Remove all existing TRs from the table
    while (tBody.firstChild) {
        tBody.removeChild(tBody.firstChild);
    }

    // Re-add the newly filtered rows
    tBody.append(...filteredRows);

}
