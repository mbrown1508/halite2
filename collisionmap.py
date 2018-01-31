import math
import hlt
import pickle
import logging


CELL_SIZE = 32


def test_aabb_circle(rect_x, rect_y, rect_w, rect_h, circ_center, radius):

    x_half_rect = rect_w / 2.0
    y_half_rect = rect_h / 2.0
    x_dist = abs(circ_center.x - rect_x - x_half_rect)
    y_dist = abs(circ_center.y - rect_y - y_half_rect)

    if x_dist > x_half_rect + radius: return False
    if y_dist > y_half_rect + radius: return False

    if x_dist <= x_half_rect: return True
    if y_dist <= y_half_rect: return True

    ## Distance from rectangle side to circle center
    dx = x_dist - x_half_rect
    dy = y_dist - y_half_rect

    return (dx**2 + dy**2) <= radius**2


class CollisionMap:
    def __init__(self, game_map):
        self.game_map = game_map

        self.width = int(math.ceil(game_map.width / CELL_SIZE))
        self.height = int(math.ceil(game_map.height / CELL_SIZE))

        self.cells = [[[] for _ in range(self.width)] for _ in range(self.height)]

        self.rebuild()

    def rebuild(self, ignore_enemy_collisions=True):
        for player in self.game_map.all_players():
            if ignore_enemy_collisions:
                if player != self.game_map.get_me():
                    continue
            for ship in player.all_ships():
                pair_id = [player.id, ship.id]
                radius = self.event_horizon(ship)
                self.add(ship, radius, pair_id)

    def add(self, ship, radius, id):
        for cell_x in range(self.width):
            for cell_y in range(self.height):
                if test_aabb_circle(cell_x * CELL_SIZE, cell_y * CELL_SIZE, CELL_SIZE, CELL_SIZE, ship, radius):
                    self.cells[cell_y][cell_x].append(id)

    def test(self, ship):
        potential_collisions = []
        for cell_x in range(self.width):
            for cell_y in range(self.height):
                radius = self.event_horizon(ship)
                if test_aabb_circle(cell_x * CELL_SIZE, cell_y * CELL_SIZE, CELL_SIZE, CELL_SIZE, ship, radius):
                    cell = self.cells[cell_y][cell_x]
                    potential_collisions += cell

        return potential_collisions

    def collision_time(self, r, ship, entity):
        dx = ship.x - entity.x
        dy = ship.y - entity.y
        dvx = ship.vel_x - entity.vel_x
        dvy = ship.vel_y - entity.vel_y

        ## Quadratic formula
        a = dvx**2 + dvy**2
        b = 2 * ((dx * dvx) + (dy * dvy))
        c = (dx**2) + (dy**2) - (r**2)

        disc = b**2 - 4 * a * c

        if a == 0.0:
            if b == 0.0:
                if c <= 0.0:
                    ## Implies r^2 >= dx^2 + dy^2 and the two are already colliding
                    return (True, 0.0)
                return (False, 0.0)
            t = -c / b
            if t >= 0.0:
                return (True, t)
            return (False, 0.0)

        elif disc == 0.0:
            ## One solution
            t = -b / (2 * a)
            return (True, t)
        elif disc > 0:
            t1 = -b + math.sqrt(disc)
            t2 = -b - math.sqrt(disc)

            if t1 >= 0.0 and t2 >= 0.0:
                return [True, min(t1, t2) / (2 * a)]
            elif t1 <= 0.0 and t2 <= 0.0:
                return [True, max(t1, t2) / (2 * a)]
            else:
                return [True, 0.0]
        else:
            return [False, 0.0]

    # The program currently has no need for attacks
    # def might_attack(self, distance, ship1, ship2):
    #     return distance <= (ship1.magnitude + ship2.magnitude + ship1.radius + ship2.radius + hlt.constants.WEAPON_RADIUS)

    def might_collide(self, distance, ship, entity):
        return distance <= ship.magnitude + entity.magnitude + ship.radius + entity.radius

    def find_events(self, id1, id2, ship1, ship2):
        """
        :param id1 [player_id, ship_id] 1
        :param id2 [player_id, ship_id] 2
        :param ship1 ship 1
        :param ship2 ship 1
        :return: All of the unsorted events found
        :rtype: list
        """

        unsorted_events = []
        distance = ship1.calculate_distance_between(ship2)
        #player1 = self.game_map.get_player(id1[0])
        #player2 = self.game_map.get_player(id2[0])

        # The program currently has no need for attacks
        # if player1 != player2 and self.might_attack(distance, ship1, ship2):
        #     ## Combat event
        #     attack_radius = ship1.radius + ship2.radius + hlt.constants.WEAPON_RADIUS
        #     t = self.collision_time(attack_radius, ship1, ship2)
        #     if t[0] and (t[1] >= 0) and (t[1] <= 1):
        #         unsorted_events.append(['Attack', id1, id2, t[1]])
        #     elif (distance < attack_radius):
        #         unsorted_events.append(['Attack', id1, id2, 0])

        #logging.info()

        #logging.info('{} {} {} {} {}'.format(id1, id2, distance, ship1, ship2))
        if (id1 != id2) and self.might_collide(distance, ship1, ship2):
            ## Collision event
            collision_radius = ship1.radius + ship2.radius

            t = self.collision_time(collision_radius, ship1, ship2)
            #logging.info(t)
            if t[0]:
                if (t[1] >= 0) and (t[1] <= 1):
                    unsorted_events.append(['Collision', id1, id2, t[1]])

                elif distance < collision_radius:
                    raise(Exception('This should never happen - the ships should already be dead'))

        return unsorted_events

    @staticmethod
    def event_horizon(ship, attack=False):
        weapon_radius = hlt.constants.WEAPON_RADIUS if attack else 0
        return ship.radius + ship.magnitude + weapon_radius


def process_events(game_map, collision_map):
    unsorted_events = []
    player = game_map.get_me()
    for ship in player.all_ships():
        unsorted_events += process_event_one_ship(game_map, collision_map, ship)
    return unsorted_events

def process_event_one_ship(game_map, collision_map, ship):
    unsorted_events = []

    player = game_map.get_me()

    id1 = [player.id, ship.id]
    ship1 = ship

    potential_collisions = []
    potential_collisions += collision_map.test(ship)

    #logging.info(potential_collisions)

    for id2 in potential_collisions:
        ship2 = game_map.get_player(id2[0]).get_ship(id2[1])
        #logging.info(ship2)
        unsorted_events += collision_map.find_events(id1, id2, ship1, ship2)

    # Possible ship-planet collisions
    for planet in game_map.all_planets():
        if planet.health <= 0:
            continue
        distance = ship1.calculate_distance_between(planet)
        if distance <= ship1.magnitude + ship1.radius + planet.radius:
            collision_radius = ship1.radius + planet.radius
            t = collision_map.collision_time(collision_radius, ship1, planet)
            if t[0]:
                if (t[1] >= 0) and (t[1] <= 1):
                    unsorted_events.append(['Collision', id1, [None, planet.id], t[1]])
                elif distance <= collision_radius:
                    #raise(Exception('This should never happen - they should already have collided'))
                    continue

    final_location = ship1.get_final_location()
    if not game_map.within_bounds(final_location):
        time = 1000000.0
        if ship1.vel_x != 0.0:
            t1 = -ship1.x / ship1.vel_x
            if (t1 < time) and (t1 >= 0):
                time = t1
            t2 = (game_map.width - ship1.x) / ship1.vel_x
            if (t2 < time) and (t2 >= 0):
                time = t2

        if ship1.vel_y != 0.0:
            t3 = -ship1.y / ship1.vel_y
            if (t3 < time) and (t3 >= 0):
                time = t3
            t4 = (game_map.height - ship1.y) / ship1.vel_y
            if (t4 < time) and (t4 >= 0):
                time = t4

        unsorted_events.append(['Desertion', id1, id1, time])

    return unsorted_events
