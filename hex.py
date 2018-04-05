from graphics import *
import shapely.geometry as s
import math
import random
import heapq
import time
import copy
import sqlite3

conn = sqlite3.connect('hex.db')
#conn = sqlite3.connect(':memory:')
c = conn.cursor()
BOARD_SIZE = 4

class bcolors:
	RED = '\033[91m'
	BLUE = '\u001b[34m'
	BLACK = '\u001b[30m'
	WHITE = '\u001b[37m'

class Board:
	def __init__(self, dims):
		self.dims = dims
		self.board = []
		for i in range(dims[0]):
			self.board.append([])
			for j in range(dims[1]):
				self.board[i].append(0)

	def get_node(self, pos):
		return self.board[pos[0]][pos[1]]

class Graphics:
	win = None
	def __init__(self, board):
		self.win = GraphWin(width = 860, height = 860, autoflush=False)
		self.board = board
		self.update_board(board)
		#self.win.getMouse()

	def clear(self, win):
		for item in win.items[:]:
			item.undraw()
		win.update()

	def update_board(self, board):
		self.board = board
		for i in range(self.board.dims[0]):
			for j in range(self.board.dims[1]):
					hex = self.hexagon(29, 500-i*26+j*26, i*45+50+j*45)
					if i == 0 and j == 0 or  \
						i == 0 and j == self.board.dims[1]-1 or \
						i == self.board.dims[0]-1 and j == 0 or \
						i == self.board.dims[0]-1 and j == self.board.dims[1]-1: 
						hex.setOutline('green')
					elif j == 0 or j == self.board.dims[1]-1: hex.setOutline('blue')
					elif i == 0 or i == self.board.dims[0]-1: hex.setOutline('red')
					if board.board[i][j] == 'B': hex.setFill('blue')
					elif board.board[i][j] == 'R': hex.setFill('red')
					hex.draw(self.win)
		self.win.update()

	def hexagon(self, r, x, y):
		points = []
		for i in range(6):
			points.append(Point(x + r*math.cos(i*2*math.pi/6), y + r*math.sin(i*2*math.pi/6)))
		return self.rotate_polygon(Polygon(points), 30)

	def get_click(self):
		while True:
			click = self.win.getMouse()
			p1 = (click.x, click.y)

			for i in range(self.board.dims[0]):
				for j in range(self.board.dims[1]):
					hex = self.hexagon(29, 500-i*26+j*26, i*45+50+j*45)
					hex_points = []
					for k in hex.getPoints():
						hex_points.append((k.x, k.y))
					if s.Point(p1).within(s.Polygon(hex_points)):
						#print((i,j))
						return (i,j)

		return False

	def rotate_polygon(self, polygon, degrees):
		theta = math.radians(degrees)  # Convert angle to radians
		cosang, sinang = math.cos(theta), math.sin(theta)

		points = polygon.getPoints()
		# find center point of Polygon to use as pivot
		n = len(points)
		cx = sum(p.getX() for p in points) / n
		cy = sum(p.getY() for p in points) / n

		new_points = []
		for p in points:
			x, y = p.getX(), p.getY()
			tx, ty = x-cx, y-cy
			new_x = ( tx*cosang + ty*sinang) + cx
			new_y = (-tx*sinang + ty*cosang) + cy
			new_points.append(Point(new_x, new_y))

		rotated_ploygon = polygon.clone()  # clone to get current attributes
		rotated_ploygon.points = new_points
		return rotated_ploygon

class Hex:
	def __init__(self, b, graphics):
		self.b = b
		self.graphics = graphics
		self.current_run_board_states_red = {}
		self.current_run_board_states_blue = {}

		#self.state_dictionary = STATES

	def run(self, red, blue, lr=0.01, verbose=True):
		winner = False
		turn = 'B'
		num_turns = 0
		while not winner:
			num_turns+=1
			if verbose:
				if turn == 'B':
					pass#print("\nIt's "+bcolors.BLUE+'█'+bcolors.BLACK+"\'s  turn!")
				else:
					pass#print("\nIt's "+bcolors.RED+'█'+bcolors.BLACK+"\'s  turn!")

			if turn == 'R' and red == '1' or turn == 'B' and blue == '1':
				move = self.get_move_from_click()
			else:
				move = self.run_lri(turn, self.b.board)
			self.play_move(move, turn)
			winner = self.is_win_state()
			if winner:
				columns = '('+','.join('?' for _ in range(BOARD_SIZE**2+1))+')'
				if winner == 'B':
					for i in self.current_run_board_states_blue.keys():
						c.execute("SELECT * FROM states WHERE state='%s'" % str(i).replace("\'",""))

						entry = c.fetchone()
						#print(entry[1:])
						new_probs = self.lri(list(entry[1:]), self.current_run_board_states_blue[i][0], lr, self.current_run_board_states_blue[i][1])
						#print(new_probs)
						#print("\/ incorrect")
						#print([entry[0]]+new_probs)

						c.execute("INSERT OR REPLACE INTO states VALUES "+columns, ([entry[0]] + new_probs))
				else:
					for i in self.current_run_board_states_red.keys():
						c.execute("SELECT * FROM states WHERE state='%s'" % str(i).replace("\'",""))
						entry = c.fetchone()
						#print(entry[1:])

						new_probs = self.lri(list(entry[1:]), self.current_run_board_states_red[i][0], lr, self.current_run_board_states_red[i][1])
						#print("\/ incorrect")
						#print([entry[0]]+new_probs)
						#print(new_probs)
						#print([entry[0].split()])
						c.execute("INSERT OR REPLACE INTO states VALUES "+columns, ([entry[0]] + new_probs))


				#t = time.time()
				#STATES = self.state_dictionary # update global variable
				#print("subtime = " + str(round(time.time()-t,5)) + " seconds")
				
				
				if verbose: print(winner+" wins!")
				

			turn = 'R' if turn == 'B' else 'B'
		return winner

	def get_move_from_click(self):
		while True:
			move = self.graphics.get_click()
			if move in self.possible_moves(self.b.board): return move

	def alpha_beta(self, player, heuristic, ply=1):
		infinite = float('inf')
		opponent = 'R' if player == 'B' else 'R'
		node_count = 0

		def max_value(board, alpha, beta, ply):
			if ply == 0 or not self.is_win_state() == False:
				score = heuristic(player, board)
				return score
			v = -infinite
			successors = self.get_successors(player, board)
			nonlocal node_count
			i = 0
			for (_,s) in successors:
				node_count +=1
				v = max(v, min_value(s, alpha, beta, ply-1))
				if v >= beta:
					return v
				alpha = max(alpha, v)
			return v

		def min_value(board, alpha, beta, ply):
			if ply == 0 or not self.is_win_state() == False:
				score = heuristic(player, board)
				return score
			v = infinite
			successors = self.get_successors(player, board)
			nonlocal node_count
			for (_,s) in successors:
				node_count += 1
				v = min(v, max_value(s, alpha, beta, ply-1))
				if v <= alpha:
					return v
				beta = min(beta, v)
			return v

		argmax = lambda keys, func: max(map(lambda key: (func(*key), key), keys))[1]
		successors = self.get_successors(player, self.b.board)

		action, state = argmax(successors, lambda a,b: min_value(b, -infinite, infinite, ply))
		self.current_run_board_states.append(self.flatten_board(state))

		return action

	def get_successors(self, player, board):
		successors = []
		moves = self.possible_moves(board)
		for move in moves:
			successors.append((move, self.play_move(move, player, execute=False)))
		return successors

	def get_neighbours(self, pos):
		neighbours = [(pos[0],pos[1]-1), (pos[0]-1,pos[1]), (pos[0]+1,pos[1]-1), \
						(pos[0]-1,pos[1]+1), (pos[0]+1,pos[1]), (pos[0],pos[1]+1)]

		return [item for item in neighbours if \
				item[0] >= 0 and \
				item[1] >= 0 and \
				item[0] <= self.b.dims[0]-1 and \
				item[1] <= self.b.dims[1]-1]

	def is_win_state(self):
		# red
		checked = [[False for i in range(self.b.dims[0])] for j in range(self.b.dims[1])]
		queue = []
		for j in range(self.b.dims[1]):
			if self.b.board[0][j] == 'R':
				heapq.heappush(queue, (0, j, self.b.board[0][j]))
				checked[0][j] = True
			while queue:
				node = heapq.heappop(queue)
				for neighbour in self.get_neighbours((node[0],node[1])):
					if neighbour and checked[neighbour[0]][neighbour[1]] == False and self.b.board[neighbour[0]][neighbour[1]] == 'R':
						if neighbour[0] == self.b.dims[0]-1: return 'R'
						heapq.heappush(queue, (neighbour[0], neighbour[1], self.b.board[neighbour[0]][neighbour[1]]))
						checked[neighbour[0]][neighbour[1]] = True

		# blue
		checked = [[False for i in range(self.b.dims[0])] for j in range(self.b.dims[1])]
		queue = []
		for i in range(self.b.dims[0]):
			if self.b.board[i][0] == 'B':
				heapq.heappush(queue, (i, 0, self.b.board[i][0]))
				checked[i][0] = True
			while queue:
				node = heapq.heappop(queue)
				for neighbour in self.get_neighbours((node[0],node[1])):
					if neighbour and checked[neighbour[0]][neighbour[1]] == False and self.b.board[neighbour[0]][neighbour[1]] == 'B':
						if neighbour[1] == self.b.dims[1]-1: return 'B'
						heapq.heappush(queue, (neighbour[0], neighbour[1], self.b.board[neighbour[0]][neighbour[1]]))
						checked[neighbour[0]][neighbour[1]] = True
		
		return False
			
	def play_move(self, move, player, execute=True):
		if execute == True:
			try:
				self.b.board[move[0]][move[1]] = player
			except:
				print(move)
				print(move[0])
				print(move[1])
				print(self.b.board)

			if self.graphics: self.graphics.update_board(self.b)
			return True
		else:
			b = [x[:] for x in self.b.board]
			b[move[0]][move[1]] = player
			return b

	def random_move(self):
		moves = self.possible_moves(self.b.board)
		return moves[random.randint(0,len(moves)-1)]

	def flatten_board(self, board):
		return tuple([item for sublist in board for item in sublist])

	def lri(self, probabilities, i, alpha, R=4):
		probabilities[i] += alpha * (1 - probabilities[i])
		for j in (y for y in range(R) if y != i):
			probabilities[j] -= alpha * probabilities[j]

		return [round(x,5) for x in probabilities]
		#return probabilities

	def run_lri(self, player, board):
		flat_board = self.flatten_board(board)
		c.execute("SELECT * FROM states WHERE state='%s'" % str(flat_board).replace("\'",""))
		result = c.fetchone()
		if result:
			probabilities = result[1:]
		else:
			probabilities = []
			possible_moves = self.possible_moves(board)
			for i in range(BOARD_SIZE**2):
				if tuple((i//BOARD_SIZE, i%BOARD_SIZE)) in possible_moves:
					probabilities.append(round(1/len(possible_moves),5))
				else:
					probabilities.append(0)

			columns = '('+','.join('?' for _ in range(BOARD_SIZE**2+1))+')'

			#print("\/ correct")
			#print([str(flat_board).replace("\'","")] + probabilities)
			c.execute("INSERT OR REPLACE INTO states VALUES "+columns, ([str(flat_board).replace("\'","")] + probabilities))

		n = random.random()
		for i in range(len(probabilities)):
			n -= probabilities[i]
			if n <= 0:
				if player == 'R': 
					self.current_run_board_states_red[flat_board] = (i, len(probabilities))
				else:
					self.current_run_board_states_blue[flat_board] = (i, len(probabilities))
				#print("made it here")
				return (i//BOARD_SIZE, i%BOARD_SIZE)
		return (BOARD_SIZE-1, BOARD_SIZE-1) # if truncation breaks code return last value

	def possible_moves(self, board):
		moves = []
		for i in range(len(board)):
			for j in range(len(board[i])):
				if board[i][j] == 0: moves.append((i,j))
		return moves

def main():
	
	c.execute("DROP TABLE states;")
	c.execute("CREATE TABLE IF NOT EXISTS states (state varchar(255) primary key);")
	for i in range(BOARD_SIZE):
		for j in range(BOARD_SIZE):
			c.execute("ALTER TABLE states ADD `%s%s` real" % (i,j))
	
	while True:
		p1 = input("\nWho is playing as RED?\n  1. Human\n  2. AI\n")
		#p1 = 2
		try:
			if int(p1) >= 1 and int(p1) <= 2: break
			else: print("Invalid entry, try again.\n")
		except ValueError: 
			print("Invalid entry, try again.\n")
	while True:
		p2 = input("\nWho is playing as BLUE?\n  1. Human\n  2. AI\n")
		#p2 = 2
		try:
			if int(p2) >= 1 and int(p2) <= 2: break
			else: print("Invalid entry, try again.\n")
		except ValueError: 
			print("Invalid entry, try again.\n")

	if p1 == p2 and p1 == '2':
		while True:
			learn = input("\nLearn or Play?\n  1. Learn\n  2. Play\n")
			try:
				if int(learn) >= 1 and int(learn) <= 2: break
				else: print("Invalid entry, try again.\n")
			except ValueError: 
				print("Invalid entry, try again.\n")
	else:
		learn = 2

	iterations = 500000

	results = []

	track_after = 1000

	if learn == '1':
		for i in range(iterations):
			if i % track_after == 0: t = time.time()
			b = Board((BOARD_SIZE,BOARD_SIZE))
			h = Hex(b, None)
			h.run(p1, p2, verbose=False)
			#print("subtime = " + str(round(time.time()-t,2)) + " seconds")
			if i % track_after == track_after-1: print(str(round((i+1)/iterations*100,2)) +"% - "+str(track_after)+" games took " + str(round(time.time()-t, 2)) + " seconds.\n")
	else:
		for _ in range(iterations):
			b = Board((BOARD_SIZE,BOARD_SIZE))
			g = Graphics(b)
			h = Hex(b, g)
			winner = h.run(p1, p2, verbose=True)
			results.append(winner)
			if len(results) > 10: results = results[len(results)-10:]
			r_count = 0
			for i in range(len(results)):
				if results[i] == 'R': r_count+=1
			print("red last 10 win% = " + str(100*r_count/min(10, len(results)))+ "%")

	conn.commit()
	conn.close()


if __name__ == '__main__':
	#with open('states.pkl', 'rb') as f:
	#t = time.time()

	#print(time.time()-t)
	try:
		main()
	except KeyboardInterrupt:
		conn.commit()
		conn.close()
		#print("saving states, do not exit until this is done...")
		#with open('states.pkl', 'wb') as f:
		#	dill.dump(STATES, f)

		print('done')
		try:
			sys.exit(0)
		except SystemExit:
			os._exit(0)