report = []

async function getProjects() {
    projects = await eel.get_projects()()

    d3.select("body")
        .append("div")
        .attr("id", "main-wrapper")
        .append("div")
        .attr("id", "header-main")
        .append("h3")
        .text("Projects")

    d3.select("#main-wrapper")
        .append("div")
        .attr("id", "project-wrapper")

    projectBoxes = d3.select("#project-wrapper")
        .selectAll("div")
        .data(projects)
        .enter()
        .append("div")
        .attr("class", "project-box")
        .on("click", function (e, d) {
            getProject(d.project_name)
        })

    newProject = d3.select("#project-wrapper")
        .insert("div", ":first-child")
        .attr("id", "new-project")
        .attr("class", "project-box")
        .append("h3")
        .text("New Project")

    projectBoxes.append("h3")
        .text(d => d.project_name)

    projectBoxes.append("p")
        .text(d => "Saved:\t" + d.saved)

    projectBoxes.append("p")
        .text(d => "Downloaded:\t" + d.downloaded)
}


function clearScreen() {
    d3.select("#project-wrapper")
        .selectAll("div")
        .remove()
}


async function getProject(project_name) {

    d3.select("#main-wrapper")
        .select("h3")
        .text(project_name)

    d3.select("#project-wrapper")
        .selectAll("div")
        .remove()

    d3.select("#project-wrapper")
        .attr("class", "opened")

    add_vid = d3.select("#header-main")
        .append("div")
        .attr("id", "add-vid-button")
        .text("+")

    add_vid.on("click", function () {
        addVideo(project_name)
    })


    report = await eel.set_project_dir(project_name)()

    setTablev2(report)

}

getProjects()