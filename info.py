from collections import OrderedDict
import logging
import hlt

class Info:
    def __init__(self):
        self.turn = -1

    def update_info(self, game_map):
        self.game_map = game_map
        self.turn += 1

        self.team_ships = self.game_map.get_me().all_ships()
        self.all_ships = self.game_map._all_ships()
        self.enemy_ships = [ship for ship in self.game_map._all_ships() if ship not in self.team_ships]

        self.my_ship_count = len(self.team_ships)
        self.enemy_ship_count = len(self.enemy_ships)
        self.all_ship_count = len(self.all_ships)

        self.my_id = self.game_map.get_me().id

        self.empty_planet_sizes = {}
        self.our_planet_sizes = {}
        self.enemy_planet_sizes = {}

        self.empty_planets = []
        self.our_planets = []
        self.enemy_planets = []

        for p in self.game_map.all_planets():
            radius = p.radius
            if not p.is_owned():
                self.empty_planet_sizes[radius] = p
                self.empty_planets.append(p)
            elif p.owner.id == self.game_map.get_me().id:
                self.our_planet_sizes[radius] = p
                self.our_planets.append(p)
            elif p.owner.id != self.game_map.get_me().id:
                self.enemy_planet_sizes[radius] = p
                self.enemy_planets.append(p)

        self.hm_our_planets = len(self.our_planet_sizes)
        self.hm_empty_planets = len(self.empty_planet_sizes)
        self.hm_enemy_planets = len(self.enemy_planet_sizes)

        self.empty_planet_keys = sorted([k for k in self.empty_planet_sizes])[::-1]
        self.our_planet_keys = sorted([k for k in self.our_planet_sizes])[::-1]
        self.enemy_planet_keys = sorted([k for k in self.enemy_planet_sizes])[::-1]

        self.all_ship_data = []

        for ship in self.game_map.get_me().all_ships():
            ship_data = {}
            ship_data['ship_id'] = ship.id
            entities_by_distance = self.game_map.nearby_entities_by_distance(ship)
            entities_by_distance = OrderedDict(sorted(entities_by_distance.items(), key=lambda t: t[0]))
            #
            # ship_data['closest_empty_planets'] = [entities_by_distance[distance][0] for distance in entities_by_distance if
            #                          isinstance(entities_by_distance[distance][0], hlt.entity.Planet) and not
            #                          entities_by_distance[distance][0].is_owned()]
            # ship_data['closest_empty_planet_distances'] = [distance for distance in entities_by_distance if
            #                                   isinstance(entities_by_distance[distance][0], hlt.entity.Planet) and not
            #                                   entities_by_distance[distance][0].is_owned()]
            #
            # ship_data['closest_my_planets'] = [entities_by_distance[distance][0] for distance in entities_by_distance if
            #                       isinstance(entities_by_distance[distance][0], hlt.entity.Planet) and
            #                       entities_by_distance[distance][0].is_owned() and (
            #                       entities_by_distance[distance][0].owner.id == self.game_map.get_me().id)]
            # ship_data['closest_my_planets_distances'] = [distance for distance in entities_by_distance if
            #                                 isinstance(entities_by_distance[distance][0], hlt.entity.Planet) and
            #                                 entities_by_distance[distance][0].is_owned() and (
            #                                 entities_by_distance[distance][0].owner.id == self.game_map.get_me().id)]
            #
            # ship_data['closest_enemy_planets'] = [entities_by_distance[distance][0] for distance in entities_by_distance if
            #                          isinstance(entities_by_distance[distance][0], hlt.entity.Planet) and
            #                          entities_by_distance[distance][0] not in ship_data['closest_my_planets'] and
            #                          entities_by_distance[distance][0] not in ship_data['closest_empty_planets']]
            # ship_data['closest_enemy_planets_distances'] = [distance for distance in entities_by_distance if
            #                                    isinstance(entities_by_distance[distance][0], hlt.entity.Planet) and
            #                                    entities_by_distance[distance][0] not in ship_data['closest_my_planets'] and
            #                                    entities_by_distance[distance][0] not in ship_data['closest_empty_planets']]
            #
            # ship_data['closest_team_ships'] = [entities_by_distance[distance][0] for distance in entities_by_distance if
            #                       isinstance(entities_by_distance[distance][0], hlt.entity.Ship) and
            #                       entities_by_distance[distance][0] in self.team_ships]
            # ship_data['closest_team_ships_distances'] = [distance for distance in entities_by_distance if
            #                                 isinstance(entities_by_distance[distance][0], hlt.entity.Ship) and
            #                                 entities_by_distance[distance][0] in self.team_ships]
            #
            ship_data['closest_enemy_ships'] = [entities_by_distance[distance][0] for distance in entities_by_distance if
                                                isinstance(entities_by_distance[distance][0], hlt.entity.Ship) and
                                                entities_by_distance[distance][0] not in self.team_ships]
            ship_data['closest_enemy_ships_distances'] = [distance for distance in entities_by_distance if
                                                          isinstance(entities_by_distance[distance][0], hlt.entity.Ship) and
                                                          entities_by_distance[distance][0] not in self.team_ships]

            self.all_ship_data.append(ship_data)

        self.all_planet_data = []
        self.largest_planet = 0

        for planet in self.enemy_planets + self.our_planets + self.empty_planets:
            planet_data = {}
            planet_data['planet_id'] = planet.id

            entities_by_distance = self.game_map.nearby_entities_by_distance(planet)
            entities_by_distance = OrderedDict(sorted(entities_by_distance.items(), key=lambda t: t[0]))

            if not planet.is_owned():
                planet_data['type'] = 'empty'
            elif planet.owner.id == self.game_map.get_me().id:
                planet_data['type'] = 'mine'
            else:
                planet_data['type'] = 'enemy'

            planet_data['closest_team_ships'] = [entities_by_distance[distance][0] for distance in entities_by_distance if
                                                 isinstance(entities_by_distance[distance][0], hlt.entity.Ship) and
                                                 entities_by_distance[distance][0] in self.team_ships]
            planet_data['closest_team_ships_distances'] = [distance for distance in entities_by_distance if
                                                           isinstance(entities_by_distance[distance][0],
                                                                      hlt.entity.Ship) and
                                                           entities_by_distance[distance][0] in self.team_ships]
            planet_data['closest_enemy_ships'] = [entities_by_distance[distance][0] for distance in entities_by_distance if
                                                  isinstance(entities_by_distance[distance][0], hlt.entity.Ship) and
                                                  entities_by_distance[distance][0] not in self.team_ships]
            planet_data['closest_enemy_ships_distances'] = [distance for distance in entities_by_distance if
                                                            isinstance(entities_by_distance[distance][0],
                                                                       hlt.entity.Ship) and
                                                            entities_by_distance[distance][0] not in self.team_ships]
            planet_data['closest_empty_planets'] = [entities_by_distance[distance][0] for distance in entities_by_distance
                                                    if
                                                    isinstance(entities_by_distance[distance][0], hlt.entity.Planet) and not
                                                    entities_by_distance[distance][0].is_owned()]
            planet_data['closest_empty_planet_distances'] = [distance for distance in entities_by_distance if
                                                             isinstance(entities_by_distance[distance][0],
                                                                        hlt.entity.Planet) and not
                                                             entities_by_distance[distance][0].is_owned()]
            planet_data['closest_my_planets'] = [entities_by_distance[distance][0] for distance in entities_by_distance if
                                                 isinstance(entities_by_distance[distance][0], hlt.entity.Planet) and
                                                 entities_by_distance[distance][0].is_owned() and (
                                                     entities_by_distance[distance][
                                                         0].owner.id == self.game_map.get_me().id)]
            planet_data['closest_my_planets_distances'] = [distance for distance in entities_by_distance if
                                                           isinstance(entities_by_distance[distance][0],
                                                                      hlt.entity.Planet) and
                                                           entities_by_distance[distance][0].is_owned() and (
                                                               entities_by_distance[distance][
                                                                   0].owner.id == self.game_map.get_me().id)]

            planet_data['closest_enemy_planets'] = [entities_by_distance[distance][0] for distance in entities_by_distance
                                                    if
                                                    isinstance(entities_by_distance[distance][0], hlt.entity.Planet) and
                                                    entities_by_distance[distance][0] not in planet_data[
                                                        'closest_my_planets'] and
                                                    entities_by_distance[distance][0] not in planet_data[
                                                        'closest_empty_planets']]
            planet_data['closest_enemy_planets_distances'] = [distance for distance in entities_by_distance if
                                                              isinstance(entities_by_distance[distance][0],
                                                                         hlt.entity.Planet) and
                                                              entities_by_distance[distance][0] not in planet_data[
                                                                  'closest_my_planets'] and
                                                              entities_by_distance[distance][0] not in planet_data[
                                                                  'closest_empty_planets']]

            planet_data['enemies_within_50'] = sum(1 for x in planet_data['closest_enemy_ships_distances'] if x < 50)
            planet_data['enemies_within_100'] = sum(1 for x in planet_data['closest_enemy_ships_distances'] if x < 100)
            planet_data['enemies_within_150'] = sum(1 for x in planet_data['closest_enemy_ships_distances'] if x < 150)
            planet_data['enemies_within_200'] = sum(1 for x in planet_data['closest_enemy_ships_distances'] if x < 200)

            planet_data['team_within_50'] = sum(1 for x in planet_data['closest_team_ships_distances'] if x < 50)
            planet_data['team_within_100'] = sum(1 for x in planet_data['closest_team_ships_distances'] if x < 100)
            planet_data['team_within_150'] = sum(1 for x in planet_data['closest_team_ships_distances'] if x < 150)
            planet_data['team_within_200'] = sum(1 for x in planet_data['closest_team_ships_distances'] if x < 200)

            planet_data['num_docked_ships'] = len(planet.all_docked_ships())
            planet_data['available_docks'] = planet.num_docking_spots
            if planet.num_docking_spots > self.largest_planet:
                self.largest_planet = planet.num_docking_spots

            self.all_planet_data.append(planet_data)

        self.all_planet_data = sorted(self.all_planet_data, key=lambda t: t['closest_team_ships_distances'][0])

        all_ships = []
        for player in self.game_map.all_players():
            if player != self.game_map.get_me():
                all_ships = all_ships + player.all_ships()

        self.all_enemy_ships = []
        for ship in all_ships:
            ship_data = {}
            ship_data['ship_id'] = ship.id
            ship_data['owner'] = ship.owner
            entities_by_distance = self.game_map.nearby_entities_by_distance(ship)
            entities_by_distance = OrderedDict(sorted(entities_by_distance.items(), key=lambda t: t[0]))

            ship_data['closest_team_ships'] = [entities_by_distance[distance][0] for distance in entities_by_distance if
                                               isinstance(entities_by_distance[distance][0], hlt.entity.Ship) and
                                               entities_by_distance[distance][0] in self.team_ships]
            ship_data['closest_team_ships_distances'] = [distance for distance in entities_by_distance if
                                                         isinstance(entities_by_distance[distance][0], hlt.entity.Ship) and
                                                         entities_by_distance[distance][0] in self.team_ships]

            self.all_enemy_ships.append(ship_data)

        self.all_enemy_ships = sorted(self.all_enemy_ships, key=lambda t: t['closest_team_ships_distances'][0])