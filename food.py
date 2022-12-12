import sqlite3
import json
import os
import requests
from bs4 import BeautifulSoup
from matplotlib import pyplot as plt


# Create Database
def setUpDatabase(db_name):
    path = os.path.dirname(os.path.abspath(__file__))
    conn = sqlite3.connect(path+'/'+db_name)
    cur = conn.cursor()
    return cur, conn

def scrapeWebsite(cur, conn):
    url = "https://www.eatthis.com/healthiest-foods-on-planet/"
    resp = requests.get(url)
    soup = BeautifulSoup(resp.content, 'html.parser')
    info = soup.find_all("div", class_="header-mod")
    cur.execute("CREATE TABLE IF NOT EXISTS Foods (id INTEGER PRIMARY KEY, name TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS Categories (id INTEGER PRIMARY KEY, category TEXT, count INTEGER)")
    cur.execute("SELECT * FROM Categories")
    res = cur.fetchall()
    if len(res) == 100:
        return
    elif len(res) == 0:
        id = 0
        count = 0
    else:
        id = res[-1][0] + 1
        count = res[-1][2] + 1
        category = res[-1][1]
    stop = id + 25

    while id < stop:
        # if category
        if len(info[count].contents) == 3:
            category = info[count].contents[1].text
        # else food item
        else:
            food = info[count].contents[3].text
            cur.execute("INSERT INTO Foods (id,name) VALUES (?,?)",(id,food))
            cur.execute("INSERT INTO Categories (id,category,count) VALUES (?,?,?)",(id,category,count))
            id += 1
        count += 1
    conn.commit()

def readAPI(cur, conn):
    cur.execute("CREATE TABLE IF NOT EXISTS Nutrients (id INTEGER PRIMARY KEY, calories INTEGER, protein INTEGER, fat INTEGER, carbs INTEGER)")
    # finds id to start at
    cur.execute("SELECT * FROM Nutrients")
    res = cur.fetchall()
    if len(res) == 100:
        return
    elif len(res) == 0:
        idStart = 0
    else:
        idStart = res[-1][0] + 1
    idEnd = idStart + 25
    for id in range(idStart, idEnd):
        cur.execute("SELECT name FROM Foods WHERE id=" + str(id))
        food = cur.fetchone()
        food = food[0]
        food.replace(" ", "%20")
        url = "https://api.edamam.com/api/food-database/v2/parser?app_id=a7694de5&" + \
        "app_key=d4a2dff893631bc5b3d7f1bc8ee861bc&ingr=" + food + "&nutrition-type=cooking"
        resp = requests.get(url)
        if not resp.ok:
            print('Request not set correctly')
            return None
        else:
            resp = resp.json()
            if resp['parsed']:
                data = resp['parsed'][0]['food']['nutrients']
            else:
                data = resp['hints'][0]['food']['nutrients']
            calories = int(data['ENERC_KCAL'])
            protein = int(data['PROCNT'])
            fat = int(data['FAT'])
            carbs = int(data['CHOCDF'])
            cur.execute("INSERT INTO Nutrients (id,calories,protein,fat,carbs) VALUES (?,?,?,?,?)",(id,calories,protein,fat,carbs))
    conn.commit()

def calculateAverages(cur, conn):
    '''calculate average calories, protein, fat, carbs for each food group
    return dictionary. each food group is a key, value would be a nested dictionary where
    calories, protein, fat, carbs are keys and the numbers in the database are the values
    return that dictionary.
    '''
    cur.execute("SELECT category FROM Categories")
    food_categories = cur.fetchall()
    if len(food_categories) < 100:
        return {}
    food_categories = list(set(food_categories))
    food_averages = {}
    for category in food_categories:
        cur.execute("SELECT * FROM Nutrients WHERE id IN (SELECT id FROM Categories WHERE category=?)",(category[0],))
        res = cur.fetchall()
        calories = 0
        protein = 0
        fat = 0
        carbs = 0
        for item in res:
            calories += item[1]
            protein += item[2]
            fat += item[3]
            carbs += item[4]
        food_averages[category[0]] = {'calories': calories/len(res), 'protein': protein/len(res), 'fat': fat/len(res), 'carbs': carbs/len(res)}
    return food_averages

def writeAverages(avgs_dic):
    f = open("averages.txt", "w")
    f.write("Average Calories, Protein, Fat, Carbs for each Food Group\n\n")
    for category in avgs_dic:
        f.write(category + " - Calories: " + str(int(avgs_dic[category]["calories"])) + ", Protein: " + str(int(avgs_dic[category]["protein"])) + \
        ", Fat: " + str(int(avgs_dic[category]["fat"])) + ", Carbs: " + str(int(avgs_dic[category]["carbs"])) + "\n")
    f.close()


def createAveragesGraph(food_averages):
    '''create a bar graph of the average calories, protein, fat, carbs for each food group
    '''
    categories = list(food_averages.keys())
    calories = []
    protein = []
    fat = []
    carbs = []
    for category in categories:
        calories.append(food_averages[category]['calories'])
        protein.append(food_averages[category]['protein'])
        fat.append(food_averages[category]['fat'])
        carbs.append(food_averages[category]['carbs'])

    x = categories
    y1 = calories
    y2 = protein
    y3 = fat
    y4 = carbs

    plt.bar(x, y1, color='r', width=0.5)
    plt.bar(x, y2, color='b', width=0.5)
    plt.bar(x, y3, color='g', width=0.5)
    plt.bar(x, y4, color='y', width=0.5)

    plt.xlabel('Food Groups')
    plt.ylabel('Average Nutrients')
    plt.title('Average Nutrients in Food Groups')
    plt.legend(['Calories', 'Protein', 'Fat', 'Carbs'])
    plt.xticks(rotation=90)
    plt.tight_layout()
    plt.savefig('averages.png')

def calculateMax(cur, conn):
    # calculate food with the max calories for each food group
    cur.execute("SELECT category FROM Categories")
    food_categories = cur.fetchall()
    food_categories = list(set(food_categories))
    food_max = {}
    for category in food_categories:
        cur.execute("SELECT Foods.id, Foods.name, Nutrients.calories FROM Foods JOIN Nutrients ON Foods.id = Nutrients.id \
        WHERE Foods.id IN (SELECT id FROM Categories WHERE category=?)",(category[0],))
        res = cur.fetchall()
        calories = 0
        for item in res:
            if item[2] > calories:
                calories = item[2]
                name = item[1]
        food_max[category[0]] = {'name': name, 'calories': calories}
    return food_max

def writeMax(max_dic):
    f = open("max.txt", "w")
    f.write("Food with Max Calories In Food Group\n\n")
    for category in max_dic:
        f.write(category + " - Food: " + max_dic[category]["name"] + ", Calories: " + str(max_dic[category]["calories"]) + "\n")
    f.close()

def createMaxGraph(food_max):
    categories = list(food_max.keys())
    calories = []
    names = []
    for category in categories:
        calories.append(food_max[category]['calories'])
        names.append(food_max[category]['name'])

    x = categories
    y = calories

    plt.clf()

    plt.scatter(x, y, color='r')

    plt.xlabel('Food Groups')
    plt.ylabel('Calories')
    plt.title('Food with Max Calories In Food Group')
    plt.xticks(rotation=90)
    plt.tight_layout()

    for i, name in enumerate(names):
        plt.annotate(name, (x[i], y[i]))

    plt.savefig('max.png')





def main():
    cur, conn = setUpDatabase('food.db')
    scrapeWebsite(cur, conn)
    readAPI(cur, conn)
    food_averages = calculateAverages(cur, conn)
    if food_averages:
        writeAverages(food_averages)
        createAveragesGraph(food_averages)
        food_max = calculateMax(cur, conn)
        writeMax(food_max)
        createMaxGraph(food_max)
    


if __name__ == "__main__":
    main()