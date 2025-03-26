from collections import Counter
import datetime
import shutil
import os
import komootgpx
import pandas as pd
from dash import Dash, html, dcc, callback, Output, Input, State, dash_table
import dash_bootstrap_components as dbc
import re

def sanitize(m, replacement=" "):
    # Define invalid characters for file names (Windows, Linux, Mac)
    invalid_chars = r'[_<>:"/\\|?*\x00-\x1F]'
    
    # Replace invalid characters with a safe character (default: " ")
    sanitized = re.sub(invalid_chars, replacement, m)
    
    # Trim leading/trailing spaces and prevent empty filenames
    sanitized = sanitized.strip() or "default_filename"

    return sanitized

# write basic dash app with layout
app = Dash(external_stylesheets=[dbc.themes.BOOTSTRAP])

# Requires Dash 2.17.0 or later
app.layout = [
    html.H1(children='Download your Komoot routes', style={'textAlign':'center'}),
    html.Div([
        html.Div([
            html.Div("Which tour types would you like to download?"),
            dcc.Dropdown(id="input_type", 
                         options=[{"label": "Planned", "value": "tour_planned"},
                                  {"label": "Recorded", "value": "tour_recorded"}], 
                         value=["tour_planned", "tour_recorded"],
                         multi=True),    
        ], className="col-6"),
        html.Div([
            html.Div("Distances of tours to download (selecting 200km as the upper limit will also download all tours longer than 200km)"),
            dcc.RangeSlider(id="input_distance", min=0, max=200, value=[0, 200]),
            html.Div(id="input_distance_display"),
        ], className="col-6"),
    ], className="row"),
    # Line to separate the two sections
    html.Hr(),
    html.Div([
            "A note on security:",
            html.Br(),
            "Your email and password are only used to access the Komoot API and are not stored in any persistent way. ",
            "You can verify this by checking the source code of this app on GitHub ", "here", ".",
            html.Br(),
            "That said, your password may be stored in plain text in the browser's backend while the app is running.",
            html.Br(),
            "If you are concerned about this, I recommend changing your Komoot password before and after using this app, " ,
            "particularly if you use the same password for other services.",
            html.Br(),
            "You are entirely responsible for any security breaches caused by use of this app.",
        ], className="col-10", style={"color": "red"}),
    html.Div([
        html.Div([
            html.Div("Your Komoot email:"),
            dcc.Input(id="input_email", value="", style={"width": "100%"}),   
        ], className="col-4"),
        html.Div([
            html.Div("Your Komoot password:"),
            dcc.Input(id="input_password", value="", type="password"),
        ], className="col-2"),
        html.Div([
            html.Br(),
            html.Button("View Tours", id="btn_view_button"),
        ], className="col-1"),
        html.Div([
            html.Br(),
            html.Div(id="login_status"),
        ], className="col-5"),
    ], className="row"),
    html.Hr(),
    html.Br(),
    html.Div("The tours that match your criteria are displayed in the table below:"),
    dash_table.DataTable(id="route_list", columns=[{"name": i, "id": i} for i in ["type", "sport", "date", "name", "distance", "elevation_up"]]),
    html.Br(),
    html.Div([
        "Select the format for your file names in your download:",
        html.Br(),
        dcc.Dropdown(id="input_format",
                     options=["type", "sport", "date", "name", "distance", "elevation_up"],
                     value=["date", "name", "distance", "elevation_up", "sport", "type"],
                     multi=True),
        html.Div(id="format_example")]),
    html.Br(),
    html.Button("Download Tours", id="btn_download_button"),
    dcc.Download(id="download_button"),
]

@callback(Output("input_distance_display", "children"),
              Input("input_distance", "value"))
def display_distance(input):
    return f"Distances selected {input[0]}km to {input[1]}km"

@callback(Output("format_example", "children"),
          Input("input_format", "value"))
def display_format(input):
    file_name = "_".join(input)
    file_name = re.sub("type" , "PlannedTour", file_name)
    file_name = re.sub("distance", "10km", file_name)
    file_name = re.sub("sport", "roadcycling", file_name)
    file_name = re.sub("name", "My Amazing Tour", file_name)
    file_name = re.sub("date", "2025-01-01", file_name)
    file_name = re.sub("elevation_up", "100m", file_name)
    return "Example of your selected file name type: " + file_name + ".gpx"

@callback(
    [Output("route_list", "data"),
    Output("login_status", "children")],
    Input("btn_view_button", "n_clicks"),
    State("input_email", "value"),
    State("input_password", "value"),
    State("input_type", "value"),
    State("input_distance", "value"),
    prevent_initial_call=True,
)
def func(n_clicks, input_email, input_password, input_type, input_distance):
    api = komootgpx.KomootApi()
    try:
        api.login(input_email, input_password)
    except:
        if api.user_id == "":
            return [[], "Login failed. Please check your email and password."]
    
    if len(input_type) == 1:
        api_input_type = input_type[0]
    else:
        api_input_type = "all"
    raw_tours = api.fetch_tours(tourType=api_input_type)
    del api
    
    raw_tours = {k: v for k, v in raw_tours.items()}
    tours_list = [v for k, v in raw_tours.items()]
    tours_df = pd.DataFrame(tours_list)
    filtered_tours = tours_df[tours_df["type"].isin(input_type)]
    min_distance = input_distance[0] * 1000
    max_distance = 10e12 if input_distance[1] >= 200 else input_distance[1] * 1000
    filtered_tours = filtered_tours[(filtered_tours["distance"] >= min_distance) & (filtered_tours["distance"] <= max_distance)]
    filtered_tours = filtered_tours[["type", "sport", "date", "name", "id", "distance", "elevation_up"]]
    filtered_tours["date"] = filtered_tours["date"].apply(lambda x: x[:10])
    filtered_tours["type"] = filtered_tours["type"].str.replace("tour_", "")
    filtered_tours["sport"] = filtered_tours["sport"].str.replace("_", "")
    filtered_tours["distance"] = (filtered_tours["distance"] / 1000).apply(lambda x: f"{x:,.0f}km")
    filtered_tours["elevation_up"] = filtered_tours["elevation_up"].apply(lambda x: f"{x:,.0f}m")
    
    return [filtered_tours.to_dict('records'), "Login successful - do not change these fields before pressing Download Tours"]

@callback(Output("download_button", "data"),
              Input("btn_download_button", "n_clicks"),
              State("input_email", "value"),
              State("input_password", "value"),
              State("route_list", "data"),
              State("input_format", "value"),
              prevent_initial_call=True)
def download_tours(n_clicks, input_email, input_password, tour_data, input_format):
    # Connect to the Komoot API using the login details
    api = komootgpx.KomootApi()
    api.login(input_email, input_password)
    
    # Create a temporary folder to store the GPX files
    if os.path.exists("TempFolder"):
        shutil.rmtree("TempFolder")    
    os.makedirs("TempFolder")
    
    # Create a string for the tours based on the input format
    for tour in tour_data:
        formatted_name = ""
        for format in input_format:
            formatted_name = formatted_name + sanitize(tour[format]) + "_"
        formatted_name = formatted_name[:-1]
        tour["tour_info_string"] = formatted_name
    
    # Check for uniqueness of tour_info_string 
    all_filenames = [v["tour_info_string"] for v in tour_data]
    non_unique_filenames = [item for item in all_filenames if Counter(all_filenames)[item] > 1]
    for tour in tour_data:
        if tour["tour_info_string"] in non_unique_filenames:
            tour["tour_info_string"] = f"{tour['tour_info_string']}_{tour['id']}"
            
    # Loop over tours in the table
    for tour in tour_data:
        os.makedirs(os.path.join("TempFolder", tour["tour_info_string"]))
        komootgpx.make_gpx(tour["id"], api,
                           os.path.join("TempFolder", tour["tour_info_string"]),
                           no_poi=False, skip_existing=False, tour_base=None, add_date=True, max_desc_length=-1)
    
        # Take the downloaded GPX file and move it to the TempFolder, removing the subfolder
        for file in os.listdir(os.path.join("TempFolder", tour["tour_info_string"])):
            shutil.move(os.path.join("TempFolder", tour["tour_info_string"], file), os.path.join("TempFolder", tour["tour_info_string"] + ".gpx"))
        os.rmdir(os.path.join("TempFolder", tour["tour_info_string"]))
    
    del api
    
    # Take all files in the TempFolder and zip them, then clean up the folders
    if os.path.exists("Tours.zip"):
        os.remove("Tours.zip")
    shutil.make_archive("Tours", 'zip', "TempFolder")
    download = dcc.send_file("Tours.zip")
    
    shutil.rmtree("TempFolder")
    os.remove("Tours.zip")
    
    return download

if __name__ == '__main__':
    app.run(debug=True)
    
# Add some guarantee that passwords and emails are not removed after clicking "view" before clicking "download"