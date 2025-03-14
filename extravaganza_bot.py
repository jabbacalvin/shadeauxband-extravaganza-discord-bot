import os
from dotenv import load_dotenv
import matplotlib.pyplot as plt
import io
import json
import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import logging
from datetime import datetime

load_dotenv()

ADMINS = ["smacksmackk", "titaniumbutter", "dufwha"]

team_colors = {
    "Team Armadyl": discord.Color(0x1045c1),
    "Team Bandos": discord.Color(0xda7614),
    "Team Saradomin": discord.Color(0xced817),
    "Team Zamorak": discord.Color(0xbe2633),
    "Team Zaros": discord.Color(0x4d0084),
}

with open("drops.json", "r", encoding="utf-8") as drops_file, open("team_roster.json", "r", encoding="utf-8") as roster_file:
    boss_drops = json.load(drops_file)
    team_roster = json.load(roster_file)

def save_data():
    with open("team_drop_counts.json", "w", encoding="utf-8") as f:
        json.dump(team_drop_counts, f, indent=4)
    with open("team_total_points.json", "w", encoding="utf-8") as f:
        json.dump(team_total_points, f, indent=4)

def load_data():
    global team_drop_counts, team_total_points
    try:
        with open("team_drop_counts.json", "r", encoding="utf-8") as f:
            team_drop_counts = json.load(f)
        with open("team_total_points.json", "r", encoding="utf-8") as f:
            team_total_points = json.load(f)
    except FileNotFoundError:
        team_drop_counts = {team: {} for team in team_roster}
        team_total_points = {team: 0 for team in team_roster}

class MyClient(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.announce_team_scores_ran = False

    async def on_ready(self):
        load_data()
        await self.tree.sync()
        print(f'Logged on as {self.user}!')
        self.announce_team_scores.start()
        self.send_graph.start()

    @tasks.loop(minutes=60.0)
    async def announce_team_scores(self):
        logging.info("Automatic announce_team_scores triggered.")
        channel = self.get_channel(1349758783827476583)
        if channel:
            embeds = []
            sorted_teams = sorted(team_total_points.items(), key=lambda item: item[1], reverse=True)

            for team, points in sorted_teams:
                points_display = int(points) if isinstance(points, (int, float)) and points.is_integer() else points
                team_color = team_colors.get(team, discord.Color.default())

                embed = discord.Embed(
                    description=f"**{team}:** {points_display} points",
                    color=team_color,
                )
                embeds.append(embed)

            if embeds:
                await channel.send("**Team Leaderboard:**", embeds=embeds)
            self.announce_team_scores_ran = True

    @announce_team_scores.before_loop
    async def before_announce_team_scores(self):
        await self.wait_until_ready()

    @tasks.loop(minutes=60.0)
    async def send_graph(self):
        logging.info("Automatic send_graph triggered.")
        channel = self.get_channel(1349758783827476583)
        if channel:
            try:
                # Sort teams and points by points in descending order
                sorted_teams_points = sorted(team_total_points.items(), key=lambda item: item[1])
                teams = [item[0] for item in sorted_teams_points]
                points = [item[1] for item in sorted_teams_points]

                plt.figure(figsize=(10, 6))

                colors = [
                    tuple(c / 255 for c in team_colors.get(team, discord.Color.default()).to_rgb())
                    for team in teams
                ]

                plt.barh(teams, points, color=colors)
                plt.xlabel("Total Points")
                plt.title("Team Points Leaderboard")

                plt.subplots_adjust(left=0.2)  # Adjust the left margin

                buffer = io.BytesIO()
                plt.savefig(buffer, format='png')
                buffer.seek(0)

                file = discord.File(buffer, filename="leaderboard.png")
                await channel.send(file=file)
                plt.close()
            except Exception as e:
                print(f"Error sending graph: {e}")
                await channel.send(f"An error occurred while generating or sending the graph: {e}")
        self.announce_team_scores_ran = False

intents = discord.Intents.default()
intents.message_content = True
client = MyClient(command_prefix='!', intents=intents)

async def boss_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    suggestions = [
        app_commands.Choice(name=boss, value=boss)
        for boss in boss_drops.keys()
        if current.lower() in boss.lower()
    ]
    return suggestions[:25]

async def drop_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    boss_name = interaction.namespace.boss_name
    if not boss_name:
        return []

    if boss_name in boss_drops:
        drops = boss_drops[boss_name]
        suggestions = [
            app_commands.Choice(name=drop["drop"], value=drop["drop"])
            for drop in drops
            if current.lower() in drop["drop"].lower()
        ]
        return suggestions[:25]
    return []

async def team_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    suggestions = [
        app_commands.Choice(name=team, value=team)
        for team in team_roster
        if current.lower() in team.lower()
    ]
    return suggestions[:25]

team_drop_counts = {team: {} for team in team_roster}
team_total_points = {team: 0 for team in team_roster}

logging.basicConfig(filename='bot_logs.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

@client.tree.command(name="boss_drops_all", description="Shows all boss drops and points in embeds (admin only).")
async def boss_drops_all(interaction: discord.Interaction):
    logging.info(f"User {interaction.user.name} used /boss_drops_all")
    if interaction.user.name not in ADMINS: #assuming you have ADMINS defined
        return await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)

    embeds = []
    for boss_name, drops in boss_drops.items():
        embed = discord.Embed(title=f"{boss_name} Drops", color=discord.Color.blue())

        for drop_info in drops:
            drop_name = drop_info["drop"]
            points = drop_info["points"]
            embed.add_field(name=drop_name, value=f"Points: {points}", inline=False)

            if len(embed.fields) >= 25:
              embed.add_field(name="Warning", value=f"Too many drops for {boss_name}. Some drops may not be shown.", inline=False)
              break #stop adding fields.

        embeds.append(embed)

    if not embeds:
        return await interaction.response.send_message("No boss drops found.", ephemeral=True)

    # Send embeds in batches of 10
    for i in range(0, len(embeds), 10):
        batch = embeds[i:i + 10]
        if i == 0:
            await interaction.response.send_message(embeds=batch, ephemeral=True)
        else:
            await interaction.followup.send(embeds=batch, ephemeral=True)

@client.tree.command(name="boss_drops", description="View drops and points for a boss.")
@app_commands.autocomplete(boss_name=boss_autocomplete)
async def boss_drops_command(interaction: discord.Interaction, boss_name: str):
    logging.info(f"User {interaction.user.name} used /boss_drops: boss={boss_name}")
    if boss_name not in boss_drops:
        await interaction.response.send_message(f"Boss '{boss_name}' not found.", ephemeral=True)
        return

    drops = boss_drops[boss_name]
    embed = discord.Embed(title=f"{boss_name} Drops", color=discord.Color.blue())
    for drop_info in drops:
        drop_name = drop_info["drop"]
        points = drop_info["points"]
        embed.add_field(name=drop_name, value=f"Points: {points}", inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)

@client.tree.command(name="drop", description="Enter boss drop for your team.")
@app_commands.autocomplete(boss_name=boss_autocomplete, drop_name=drop_autocomplete)
async def drop(interaction: discord.Interaction, boss_name: str, drop_name: str):
    logging.info(f"User {interaction.user.name} used /drop: boss={boss_name}, drop={drop_name}")
    member_id = str(interaction.user.name)

    team_found = None
    for team, members in team_roster.items():
        for member in members:
            if member["discord_user"] == member_id:
                team_found = team
                break
        if team_found:
            break

    if not team_found:
        return await interaction.response.send_message(f"❌ User '{member_id}' not found in any team roster.")

    if boss_name in boss_drops:
        drops = boss_drops[boss_name]
        for drop in drops:
            if drop["drop"].lower() == drop_name.lower():
                point_value = drop["points"]
                drop_name_clean = drop["drop"]

                if team_found not in team_drop_counts:
                    team_drop_counts[team_found] = {}

                if boss_name not in team_drop_counts[team_found]:
                    team_drop_counts[team_found][boss_name] = {}

                if drop_name_clean in team_drop_counts[team_found][boss_name]:
                    drop_count = team_drop_counts[team_found][boss_name][drop_name_clean]
                    original_point_value = point_value
                    if (boss_name == "Barrows Chests" or boss_name == "Moons of Peril") and drop_count >= 4:
                        point_value /= 2
                        point_value_display = int(point_value) if point_value.is_integer() else point_value
                        message_addition = f"Congratulations on a 5th drop! **{drop_name_clean}** from **{boss_name}** is worth **{point_value_display} points** since it is a 5th drop! Added to {team_found}."
                    elif not (boss_name == "Barrows Chests" or boss_name == "Moons of Peril") and drop_count >= 1:
                        point_value /= 2
                        point_value_display = int(point_value) if point_value.is_integer() else point_value
                        message_addition = f"Congratulations on a duplicate drop! **{drop_name_clean}** from **{boss_name}** is worth **{point_value_display} points** since it is a duplicate! Added to {team_found}."
                    else:
                        message_addition = f"🗡️ **{drop_name_clean}** from **{boss_name}** is worth **{point_value} points**! Added to {team_found}."
                    team_drop_counts[team_found][boss_name][drop_name_clean] += 1
                else:
                    team_drop_counts[team_found][boss_name][drop_name_clean] = 1
                    message_addition = f"🗡️ **{drop_name_clean}** from **{boss_name}** is worth **{point_value} points**! Added to {team_found}."

                team_total_points[team_found] += point_value
                save_data()

                team_color = team_colors.get(team_found, discord.Color.default())
                embed = discord.Embed(description=message_addition, color=team_color)
                return await interaction.response.send_message(embed=embed)

        return await interaction.response.send_message(f"❌ Drop '{drop_name}' not found for {boss_name}.")

    return await interaction.response.send_message(f"❌ Boss '{boss_name}' not found.")

@client.tree.command(name="drop_admin", description="Add a drop to a team (admin only).")
@app_commands.autocomplete(team_name=team_autocomplete, boss_name=boss_autocomplete, drop_name=drop_autocomplete)
async def drop_admin(interaction: discord.Interaction, team_name: str, boss_name: str, drop_name: str):
    logging.info(f"Admin {interaction.user.name} used /drop_admin: team={team_name}, boss={boss_name}, drop={drop_name}")
    if interaction.user.name not in ADMINS:
        return await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)

    if team_name not in team_roster:
        return await interaction.response.send_message(f"❌ Team '{team_name}' not found.", ephemeral=True)

    if boss_name not in boss_drops:
        return await interaction.response.send_message(f"❌ Boss '{boss_name}' not found.", ephemeral=True)

    found_drop = False
    for drop in boss_drops[boss_name]:
        if drop["drop"].lower() == drop_name.lower():
            point_value = drop["points"]
            drop_name_clean = drop["drop"]
            found_drop = True
            break

    if not found_drop:
        return await interaction.response.send_message(f"❌ Drop '{drop_name}' not found for {boss_name}.", ephemeral=True)

    if team_name not in team_drop_counts:
        team_drop_counts[team_name] = {}

    if boss_name not in team_drop_counts[team_name]:
        team_drop_counts[team_name][boss_name] = {}

    if drop_name_clean in team_drop_counts[team_name][boss_name]:
        drop_count = team_drop_counts[team_name][boss_name][drop_name_clean]
        if (boss_name == "Barrows Chests" or boss_name == "Moons of Peril") and drop_count >= 4:
            point_value /= 2
            point_value_display = int(point_value) if point_value.is_integer() else point_value
            message_addition = f"Congratulations on a 5th drop! **{drop_name_clean}** from **{boss_name}** is worth **{point_value_display} points** since it is a 5th drop! Added to {team_name}."
        elif not (boss_name == "Barrows Chests" or boss_name == "Moons of Peril") and drop_count >= 1:
            point_value /= 2
            point_value_display = int(point_value) if point_value.is_integer() else point_value
            message_addition = f"Congratulations on a duplicate drop! **{drop_name_clean}** from **{boss_name}** is worth **{point_value_display} points** since it is a duplicate! Added to {team_name}."
        else:
            message_addition = f"🗡️ **{drop_name_clean}** from **{boss_name}** is worth **{point_value} points**! Added to {team_name}."
        team_drop_counts[team_name][boss_name][drop_name_clean] += 1
    else:
        team_drop_counts[team_name][boss_name][drop_name_clean] = 1
        message_addition = f"🗡️ **{drop_name_clean}** from **{boss_name}** is worth **{point_value} points**! Added to {team_name}."

    team_total_points[team_name] += point_value
    save_data()

    team_color = team_colors.get(team_name, discord.Color.default())
    embed = discord.Embed(description=message_addition, color=team_color)
    return await interaction.response.send_message(embed=embed)

@client.tree.command(name="remove_drop", description="Remove a boss drop.")
@app_commands.autocomplete(boss_name=boss_autocomplete, drop_name=drop_autocomplete)
async def remove_drop(interaction: discord.Interaction, boss_name: str, drop_name: str):
    logging.info(f"User {interaction.user.name} used /remove_drop: boss={boss_name}, drop={drop_name}")
    member_id = str(interaction.user.name)
    team_found = None
    for team, members in team_roster.items():
        for member in members:
            if member["discord_user"] == member_id and member["role"] == "leader":
                team_found = team
                break
        if team_found:
            break

    if not team_found:
        return await interaction.response.send_message("Only team leaders can use this command.")

    if boss_name in team_drop_counts[team_found] and drop_name in team_drop_counts[team_found][boss_name]:
        drop_count = team_drop_counts[team_found][boss_name][drop_name]
        if drop_count > 0:
            drops = boss_drops[boss_name]
            for drop in drops:
                if drop["drop"].lower() == drop_name.lower():
                    point_value = drop["points"]
                    if (boss_name == "Barrows Chests" or boss_name == "Moons of Peril") and drop_count > 4:
                        point_value /= 2
                    elif drop_count > 1:
                        point_value /= 2

                    team_total_points[team_found] -= point_value
                    team_drop_counts[team_found][boss_name][drop_name] -= 1
                    if team_drop_counts[team_found][boss_name][drop_name] == 0:
                        del team_drop_counts[team_found][boss_name][drop_name]
                        if not team_drop_counts[team_found][boss_name]:
                            del team_drop_counts[team_found][boss_name]
                    save_data()

                    team_color = team_colors.get(team_found, discord.Color.default())
                    embed = discord.Embed(description=f"Removed 1 {drop_name} from {boss_name} for {team_found}.", color=team_color)
                    return await interaction.response.send_message(embed=embed)
        else:
            return await interaction.response.send_message(f"❌ No {drop_name} found for {boss_name} to remove.")

    return await interaction.response.send_message(f"❌ No {drop_name} found for {boss_name} to remove.")

@client.tree.command(name="remove_drop_admin", description="Remove a boss drop from a team (admin only).")
@app_commands.autocomplete(team_name=team_autocomplete, boss_name=boss_autocomplete, drop_name=drop_autocomplete)
async def remove_drop_admin(interaction: discord.Interaction, team_name: str, boss_name: str, drop_name: str):
    logging.info(f"Admin {interaction.user.name} used /remove_drop_admin: team={team_name}, boss={boss_name}, drop={drop_name}")
    if interaction.user.name not in ADMINS:
        return await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)

    if team_name not in team_roster:
        return await interaction.response.send_message(f"❌ Team '{team_name}' not found.", ephemeral=True)

    if boss_name in team_drop_counts[team_name] and drop_name in team_drop_counts[team_name][boss_name]:
        drop_count = team_drop_counts[team_name][boss_name][drop_name]
        if drop_count > 0:
            drops = boss_drops[boss_name]
            for drop in drops:
                if drop["drop"].lower() == drop_name.lower():
                    point_value = drop["points"]
                    if (boss_name == "Barrows Chests" or boss_name == "Moons of Peril") and drop_count > 4:
                        point_value /= 2
                    elif drop_count > 1:
                        point_value /= 2

                    team_total_points[team_name] -= point_value
                    team_drop_counts[team_name][boss_name][drop_name] -= 1
                    if team_drop_counts[team_name][boss_name][drop_name] == 0:
                        del team_drop_counts[team_name][boss_name][drop_name]
                        if not team_drop_counts[team_name][boss_name]:
                            del team_drop_counts[team_name][boss_name]
                    save_data()

                    team_color = team_colors.get(team_name, discord.Color.default())
                    embed = discord.Embed(description=f"Removed 1 {drop_name} from {boss_name} for {team_name}.", color=team_color)
                    return await interaction.response.send_message(embed=embed)
        else:
            return await interaction.response.send_message(f"❌ No {drop_name} found for {boss_name} to remove.", ephemeral=True)

    return await interaction.response.send_message(f"❌ No {drop_name} found for {boss_name} for {team_name} to remove.", ephemeral=True)

@client.tree.command(name="team_stats_all", description="View drop counts and total points for all teams.")
async def team_stats_all(interaction: discord.Interaction):
    logging.info(f"User {interaction.user.name} used /team_stats_all")
    embeds = []
    for team, bosses in team_drop_counts.items():
        team_color = team_colors.get(team, discord.Color.default())
        embed = discord.Embed(title=f"{team} Stats", color=team_color)
        stats_text = ""
        for boss_name, drops in bosses.items():
            for drop_name, count in drops.items():
                stats_text += f"- {drop_name} from {boss_name}: {count} times\n"
        total_points = team_total_points[team]
        total_points_display = int(total_points) if total_points.is_integer() else total_points
        stats_text += f"**Total Points: {total_points_display}**\n"
        embed.description = stats_text
        embeds.append(embed)

    if not embeds:
        await interaction.response.send_message("No team stats available yet.")
        return

    total_points_list = list(team_total_points.values())
    if all(points == 0 for points in total_points_list):
        leader_text = "**No team is currently leading.**"
        leader_embed = discord.Embed(description=leader_text, color=discord.Color.default())
    else:
        leader = max(team_total_points, key=team_total_points.get)
        leader_points = team_total_points[leader]
        leader_points_display = int(leader_points) if leader_points.is_integer() else leader_points
        leader_color = team_colors.get(leader, discord.Color.default())
        leader_text = f"**Current Leader:** {leader} with {leader_points_display} points."
        leader_embed = discord.Embed(description=leader_text, color=leader_color)

    sorted_teams = sorted(team_total_points.items(), key=lambda item: item[1], reverse=True)
    second_place = sorted_teams[1] if len(sorted_teams) > 1 else None
    third_place = sorted_teams[2] if len(sorted_teams) > 2 else None

    leaderboard_embeds = [leader_embed]

    if second_place:
        second_place_text = f"**Second Place:** {second_place[0]} with {second_place[1]} points."
        second_place_embed = discord.Embed(description=second_place_text, color=team_colors.get(second_place[0], discord.Color.default()))
        leaderboard_embeds.append(second_place_embed)

    if third_place:
        third_place_text = f"**Third Place:** {third_place[0]} with {third_place[1]} points."
        third_place_embed = discord.Embed(description=third_place_text, color=team_colors.get(third_place[0], discord.Color.default()))
        leaderboard_embeds.append(third_place_embed)

    await interaction.response.send_message(embeds=embeds)
    await interaction.channel.send(embeds=leaderboard_embeds)

@client.tree.command(name="team_stats", description="View drop counts and total points for your team.")
async def team_stats(interaction: discord.Interaction):
    logging.info(f"User {interaction.user.name} used /team_stats")
    member_id = str(interaction.user.name)

    team_found = None
    for team, members in team_roster.items():
        for member in members:
            if member["discord_user"] == member_id:
                team_found = team
                break
        if team_found:
            break

    if not team_found:
        return await interaction.response.send_message(f"❌ User '{member_id}' not found in any team roster.")

    team_color = team_colors.get(team_found, discord.Color.default())
    embed = discord.Embed(title=f"{team_found} Stats", color=team_color)
    stats_text = ""
    for boss_name, drops in team_drop_counts[team_found].items():
        for drop_name, count in drops.items():
            stats_text += f"- {drop_name} from {boss_name}: {count} times\n"
    total_points = team_total_points[team_found]
    total_points_display = int(total_points) if total_points.is_integer() else total_points
    stats_text += f"**Total Points: {total_points_display}**\n"
    embed.description = stats_text

    await interaction.response.send_message(embed=embed)

@client.tree.command(name="show_leaderboard", description="Shows the team leaderboard and graph (admin only).")
async def show_leaderboard(interaction: discord.Interaction):
    logging.info(f"Admin {interaction.user.name} used /show_leaderboard")
    if interaction.user.name not in ADMINS:
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True) 

    try:
        await client.announce_team_scores()
        await client.send_graph()
        await interaction.followup.send("Leaderboard and graph sent!", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)

@client.tree.command(name="recalculate_points", description="Recalculate team total points from drop counts (admin only).")
async def recalculate_points(interaction: discord.Interaction):
    logging.info(f"Admin {interaction.user.name} used /recalculate_points")
    if interaction.user.name not in ADMINS:
        return await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)

    global team_total_points
    team_total_points = {team: 0 for team in team_roster}

    for team, bosses in team_drop_counts.items():
        for boss_name, drops in bosses.items():
            for drop_name, count in drops.items():
                if boss_name in boss_drops:
                    drops_info = boss_drops[boss_name]
                    for drop_info in drops_info:
                        if drop_info["drop"] == drop_name:
                            point_value = drop_info["points"]
                            original_point_value = point_value 

                            if boss_name == "Barrows Chests" or boss_name == "Moons of Peril":
                                if count > 4:
                                    point_value /= 2 
                                team_total_points[team] += point_value * count
                            else:
                                if count > 1:
                                    point_value /= 2 
                                team_total_points[team] += original_point_value * 1
                                if count > 1:
                                    team_total_points[team] += point_value * (count - 1)
                            break
    save_data()
    await interaction.response.send_message("Team total points recalculated.", ephemeral=True)

@client.tree.command(name="reset_data", description="Reset team drop counts and total points (admin only).")
async def reset_data(interaction: discord.Interaction):
    logging.info(f"Admin {interaction.user.name} used /reset_data")
    if interaction.user.name in ADMINS:
        confirm_button = discord.ui.Button(style=discord.ButtonStyle.danger, label="✅ Yes, Reset Data")
        cancel_button = discord.ui.Button(style=discord.ButtonStyle.secondary, label="❌ Cancel")

        async def confirm_callback(interaction_button: discord.Interaction):
            if interaction_button.user == interaction.user:
                global team_drop_counts, team_total_points
                team_drop_counts = {team: {} for team in team_roster}
                team_total_points = {team: 0 for team in team_roster}
                save_data()
                await interaction_button.response.send_message("Data reset and bot restarted.", ephemeral=True)
                await interaction.edit_original_response(view=None) #remove buttons
            else:
                await interaction_button.response.send_message("This is not your button to press", ephemeral=True)

        async def cancel_callback(interaction_button: discord.Interaction):
            if interaction_button.user == interaction.user:
                await interaction_button.response.send_message("Data reset cancelled.", ephemeral=True)
                await interaction.edit_original_response(view=None) #remove buttons
            else:
                await interaction_button.response.send_message("This is not your button to press", ephemeral=True)

        confirm_button.callback = confirm_callback
        cancel_button.callback = cancel_callback

        view = discord.ui.View()
        view.add_item(confirm_button)
        view.add_item(cancel_button)

        await interaction.response.send_message("Are you sure you want to reset all team data?", view=view, ephemeral=True)
    else:
        await interaction.response.send_message("You don't have permission to reset the data.", ephemeral=True)

client.run(os.environ.get("DISCORD_TOKEN"))