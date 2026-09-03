_graph = None

def get_graph():
    import osmnx as ox
    global _graph
    if _graph is None:
        print("Chargement du graphe OSM de Douala...")
        _graph = ox.graph_from_point((4.05, 9.70), dist=5000, network_type='drive')
        _graph = ox.add_edge_speeds(_graph)
        _graph = ox.add_edge_travel_times(_graph)
        print("Graphe chargé.")
    return _graph

def calculer_matrice_distances(points):
    import networkx as nx
    import numpy as np
    import osmnx as ox
    G = get_graph()
    n = len(points)
    matrice = np.zeros((n, n))

    noeuds = [ox.distance.nearest_nodes(G, lon, lat) for lat, lon in points]

    for i in range(n):
        for j in range(i+1, n):
            try:
                dist = nx.shortest_path_length(G, noeuds[i], noeuds[j], weight='length')
                matrice[i][j] = dist
                matrice[j][i] = dist
            except nx.NetworkXNoPath:
                matrice[i][j] = 1e9
                matrice[j][i] = 1e9
    return matrice

def resoudre_vrp(matrice_distances, nb_vehicules=1, capacites=None, demandes=None):
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2
    n = len(matrice_distances)
    if n < 2:
        return None

    if capacites is None:
        capacites = [1000] * nb_vehicules
    if demandes is None:
        demandes = [1] * n

    depot = 0

    manager = pywrapcp.RoutingIndexManager(n, nb_vehicules, depot)
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return int(matrice_distances[from_node][to_node])

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    def demand_callback(from_index):
        from_node = manager.IndexToNode(from_index)
        return demandes[from_node]

    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_callback_index,
        0,
        capacites,
        True,
        'Capacity'
    )

    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_parameters.time_limit.seconds = 5

    solution = routing.SolveWithParameters(search_parameters)

    if solution:
        tournees = []
        for vehicle_id in range(nb_vehicules):
            index = routing.Start(vehicle_id)
            route = []
            while not routing.IsEnd(index):
                node = manager.IndexToNode(index)
                route.append(node)
                index = solution.Value(routing.NextVar(index))
            tournees.append(route)
        return tournees
    return None
