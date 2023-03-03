let config = {heuristic: "best", metric: "euclidean", renderFreq: 10, closeFreq: 1, closeFactor: 0.2};

function map2range (value, domain_min, domain_max, range_min, range_max) {
  if (domain_min == domain_max) {
    return range_min;
  }
  if (value <= domain_min) {
    return range_min;
  }
  if (value >= domain_max) {
    return range_max;
  }
  return ((value - domain_min) * (range_max - range_min) / (domain_max - domain_min)) + range_min;
}

function ge(a, y, c, l, h) {
    var i = h + 1;
    while (l <= h) {
      var m = (l + h) >>> 1, x = a[m];
      var p = (c !== undefined) ? c(x, y) : (x - y);
      if (p >= 0) { i = m; h = m - 1 } else { l = m + 1 }
    }
    return i;
  };
  
  function gt(a, y, c, l, h) {
    var i = h + 1;
    while (l <= h) {
      var m = (l + h) >>> 1, x = a[m];
      var p = (c !== undefined) ? c(x, y) : (x - y);
      if (p > 0) { i = m; h = m - 1 } else { l = m + 1 }
    }
    return i;
  };
  
  function lt(a, y, c, l, h) {
    var i = l - 1;
    while (l <= h) {
      var m = (l + h) >>> 1, x = a[m];
      var p = (c !== undefined) ? c(x, y) : (x - y);
      if (p < 0) { i = m; l = m + 1 } else { h = m - 1 }
    }
    return i;
  };
  
  function le(a, y, c, l, h) {
    var i = l - 1;
    while (l <= h) {
      var m = (l + h) >>> 1, x = a[m];
      var p = (c !== undefined) ? c(x, y) : (x - y);
      if (p <= 0) { i = m; l = m + 1 } else { h = m - 1 }
    }
    return i;
  };
  
  function eq(a, y, c, l, h) {
    while (l <= h) {
      var m = (l + h) >>> 1, x = a[m];
      var p = (c !== undefined) ? c(x, y) : (x - y);
      if (p === 0) { return m }
      if (p <= 0) { l = m + 1 } else { h = m - 1 }
    }
    return -1;
  };
  
  function norm(a, y, c, l, h, f) {
    if (typeof c === 'function') {
      return f(a, y, c, (l === undefined) ? 0 : l | 0, (h === undefined) ? a.length - 1 : h | 0);
    }
    return f(a, y, undefined, (c === undefined) ? 0 : c | 0, (l === undefined) ? a.length - 1 : l | 0);
  }
  
  var bounds = {
    ge: function(a, y, c, l, h) { return norm(a, y, c, l, h, ge)},
    gt: function(a, y, c, l, h) { return norm(a, y, c, l, h, gt)},
    lt: function(a, y, c, l, h) { return norm(a, y, c, l, h, lt)},
    le: function(a, y, c, l, h) { return norm(a, y, c, l, h, le)},
    eq: function(a, y, c, l, h) { return norm(a, y, c, l, h, eq)}
  }
  
  var NOT_FOUND = 0
  var SUCCESS = 1
  var EMPTY = 2
  
  function IntervalTreeNode(mid, left, right, leftPoints, rightPoints) {
    this.mid = mid
    this.left = left
    this.right = right
    this.leftPoints = leftPoints
    this.rightPoints = rightPoints
    this.count = (left ? left.count : 0) + (right ? right.count : 0) + leftPoints.length
  }
  
  var proto = IntervalTreeNode.prototype
  
  function copy(a, b) {
    a.mid = b.mid
    a.left = b.left
    a.right = b.right
    a.leftPoints = b.leftPoints
    a.rightPoints = b.rightPoints
    a.count = b.count
  }
  
  function rebuild(node, intervals) {
    var ntree = createIntervalTree(intervals)
    node.mid = ntree.mid
    node.left = ntree.left
    node.right = ntree.right
    node.leftPoints = ntree.leftPoints
    node.rightPoints = ntree.rightPoints
    node.count = ntree.count
  }
  
  function rebuildWithInterval(node, interval) {
    var intervals = node.intervals([])
    intervals.push(interval)
    rebuild(node, intervals)    
  }
  
  function rebuildWithoutInterval(node, interval) {
    var intervals = node.intervals([])
    var idx = intervals.indexOf(interval)
    if(idx < 0) {
      return NOT_FOUND
    }
    intervals.splice(idx, 1)
    rebuild(node, intervals)
    return SUCCESS
  }
  
  proto.intervals = function(result) {
    result.push.apply(result, this.leftPoints)
    if(this.left) {
      this.left.intervals(result)
    }
    if(this.right) {
      this.right.intervals(result)
    }
    return result
  }
  
  proto.insert = function(interval) {
    var weight = this.count - this.leftPoints.length
    this.count += 1
    if(interval[1] < this.mid) {
      if(this.left) {
        if(4*(this.left.count+1) > 3*(weight+1)) {
          rebuildWithInterval(this, interval)
        } else {
          this.left.insert(interval)
        }
      } else {
        this.left = createIntervalTree([interval])
      }
    } else if(interval[0] > this.mid) {
      if(this.right) {
        if(4*(this.right.count+1) > 3*(weight+1)) {
          rebuildWithInterval(this, interval)
        } else {
          this.right.insert(interval)
        }
      } else {
        this.right = createIntervalTree([interval])
      }
    } else {
      var l = bounds.ge(this.leftPoints, interval, compareBegin)
      var r = bounds.ge(this.rightPoints, interval, compareEnd)
      this.leftPoints.splice(l, 0, interval)
      this.rightPoints.splice(r, 0, interval)
    }
  }
  
  proto.remove = function(interval) {
    var weight = this.count - this.leftPoints
    if(interval[1] < this.mid) {
      if(!this.left) {
        return NOT_FOUND
      }
      var rw = this.right ? this.right.count : 0
      if(4 * rw > 3 * (weight-1)) {
        return rebuildWithoutInterval(this, interval)
      }
      var r = this.left.remove(interval)
      if(r === EMPTY) {
        this.left = null
        this.count -= 1
        return SUCCESS
      } else if(r === SUCCESS) {
        this.count -= 1
      }
      return r
    } else if(interval[0] > this.mid) {
      if(!this.right) {
        return NOT_FOUND
      }
      var lw = this.left ? this.left.count : 0
      if(4 * lw > 3 * (weight-1)) {
        return rebuildWithoutInterval(this, interval)
      }
      var r = this.right.remove(interval)
      if(r === EMPTY) {
        this.right = null
        this.count -= 1
        return SUCCESS
      } else if(r === SUCCESS) {
        this.count -= 1
      }
      return r
    } else {
      if(this.count === 1) {
        if(this.leftPoints[0] === interval) {
          return EMPTY
        } else {
          return NOT_FOUND
        }
      }
      if(this.leftPoints.length === 1 && this.leftPoints[0] === interval) {
        if(this.left && this.right) {
          var p = this
          var n = this.left
          while(n.right) {
            p = n
            n = n.right
          }
          if(p === this) {
            n.right = this.right
          } else {
            var l = this.left
            var r = this.right
            p.count -= n.count
            p.right = n.left
            n.left = l
            n.right = r
          }
          copy(this, n)
          this.count = (this.left?this.left.count:0) + (this.right?this.right.count:0) + this.leftPoints.length
        } else if(this.left) {
          copy(this, this.left)
        } else {
          copy(this, this.right)
        }
        return SUCCESS
      }
      for(var l = bounds.ge(this.leftPoints, interval, compareBegin); l<this.leftPoints.length; ++l) {
        if(this.leftPoints[l][0] !== interval[0]) {
          break
        }
        if(this.leftPoints[l] === interval) {
          this.count -= 1
          this.leftPoints.splice(l, 1)
          for(var r = bounds.ge(this.rightPoints, interval, compareEnd); r<this.rightPoints.length; ++r) {
            if(this.rightPoints[r][1] !== interval[1]) {
              break
            } else if(this.rightPoints[r] === interval) {
              this.rightPoints.splice(r, 1)
              return SUCCESS
            }
          }
        }
      }
      return NOT_FOUND
    }
  }
  
  function reportLeftRange(arr, hi, cb) {
    for(var i=0; i<arr.length && arr[i][0] <= hi; ++i) {
      var r = cb(arr[i])
      if(r) { return r }
    }
  }
  
  function reportRightRange(arr, lo, cb) {
    for(var i=arr.length-1; i>=0 && arr[i][1] >= lo; --i) {
      var r = cb(arr[i])
      if(r) { return r }
    }
  }
  
  function reportRange(arr, cb) {
    for(var i=0; i<arr.length; ++i) {
      var r = cb(arr[i])
      if(r) { return r }
    }
  }
  
  proto.queryPoint = function(x, cb) {
    if(x < this.mid) {
      if(this.left) {
        var r = this.left.queryPoint(x, cb)
        if(r) { return r }
      }
      return reportLeftRange(this.leftPoints, x, cb)
    } else if(x > this.mid) {
      if(this.right) {
        var r = this.right.queryPoint(x, cb)
        if(r) { return r }
      }
      return reportRightRange(this.rightPoints, x, cb)
    } else {
      return reportRange(this.leftPoints, cb)
    }
  }
  
  proto.queryInterval = function(lo, hi, cb) {
    if(lo < this.mid && this.left) {
      var r = this.left.queryInterval(lo, hi, cb)
      if(r) { return r }
    }
    if(hi > this.mid && this.right) {
      var r = this.right.queryInterval(lo, hi, cb)
      if(r) { return r }
    }
    if(hi < this.mid) {
      return reportLeftRange(this.leftPoints, hi, cb)
    } else if(lo > this.mid) {
      return reportRightRange(this.rightPoints, lo, cb)
    } else {
      return reportRange(this.leftPoints, cb)
    }
  }
  
  function compareNumbers(a, b) {
    return a - b
  }
  
  function compareBegin(a, b) {
    var d = a[0] - b[0]
    if(d) { return d }
    return a[1] - b[1]
  }
  
  function compareEnd(a, b) {
    var d = a[1] - b[1]
    if(d) { return d }
    return a[0] - b[0]
  }
  
  function createIntervalTree(intervals) {
    if(intervals.length === 0) {
      return null
    }
    var pts = []
    for(var i=0; i<intervals.length; ++i) {
      pts.push(intervals[i][0], intervals[i][1])
    }
    pts.sort(compareNumbers)
  
    var mid = pts[pts.length>>1]
  
    var leftIntervals = []
    var rightIntervals = []
    var centerIntervals = []
    for(var i=0; i<intervals.length; ++i) {
      var s = intervals[i]
      if(s[1] < mid) {
        leftIntervals.push(s)
      } else if(mid < s[0]) {
        rightIntervals.push(s)
      } else {
        centerIntervals.push(s)
      }
    }
  
    //Split center intervals
    var leftPoints = centerIntervals
    var rightPoints = centerIntervals.slice()
    leftPoints.sort(compareBegin)
    rightPoints.sort(compareEnd)
  
    return new IntervalTreeNode(mid, 
      createIntervalTree(leftIntervals),
      createIntervalTree(rightIntervals),
      leftPoints,
      rightPoints)
  }
  
  //User friendly wrapper that makes it possible to support empty trees
  function IntervalTree(root) {
    this.root = root
  }
  
  var tproto = IntervalTree.prototype
  
  tproto.insert = function(interval) {
    if(this.root) {
      this.root.insert(interval)
    } else {
      this.root = new IntervalTreeNode(interval[0], null, null, [interval], [interval])
    }
  }
  
  tproto.remove = function(interval) {
    if(this.root) {
      var r = this.root.remove(interval)
      if(r === EMPTY) {
        this.root = null
      }
      return r !== NOT_FOUND
    }
    return false
  }
  
  tproto.queryPoint = function(p, cb) {
    if(this.root) {
      return this.root.queryPoint(p, cb)
    }
  }
  
  tproto.queryInterval = function(lo, hi, cb) {
    if(lo <= hi && this.root) {
      return this.root.queryInterval(lo, hi, cb)
    }
  }
  
  Object.defineProperty(tproto, "count", {
    get: function() {
      if(this.root) {
        return this.root.count
      }
      return 0
    }
  })
  
  Object.defineProperty(tproto, "intervals", {
    get: function() {
      if(this.root) {
        return this.root.intervals([])
      }
      return []
    }
  })
  
  function createWrapper(intervals) {
    if(!intervals || intervals.length === 0) {
      return new IntervalTree(null)
    }
    return new IntervalTree(createIntervalTree(intervals))
  }
  
  function rectangle(minCorner = [0, 0], sides = [10, 10]) {
    let [x, y] = minCorner;
    let [sidex, sidey] = sides;
    return new VList(
      new Vertex(+1, [x, y]),
      new Vertex(-1, [x + sidex, y]),
      new Vertex(-1, [x, y + sidey]),
      new Vertex(+1, [x + sidex, y + sidey])
    );
  }
  
  function topo(vlist, d) {
    if (d < 0) return erode(vlist, -d);
    else return dilate(vlist, d);
  }
  
  function union(a, b) {
    return a.add(b).transform((w) => +(w > 0));
  }
  
  function dilate (vlist, d) {
    let vtx = [];
    for (let r of vlist.rectangles()) {
      [[-d,-d],[d,-d],[-d,d],[d,d]].forEach(([dx,dy],i) => {
        r[i].p[0]+=dx;
        r[i].p[1]+=dy;
        vtx.push(r[i]);
      });
    }
    return normalizeVList(new VList(...vtx)).transform(w => +(w>0))
  }
  
  function normalizeVList(vlist) {
    if (vlist.length < 2) return vlist;
    let result = new VList();
    let prev = vlist[0];
    for (let i = 1; i < vlist.length; i++) {
      let next = vlist[i];
      if (prev.cmp(next) == 0) {
        prev.w += next.w;
      }
      else {
        if (prev.w != 0) result.push (prev)
        prev = next;
      }
    }
    if (prev.w != 0) result.push (prev)
    return result;
  }
  
  function erode(vlist,d) {
    if (vlist.length < 4) return new VList();
    // Find bounding box
    let {min,max} = boundingBox(vlist);
    for (let v of vlist) {
      for (let i of [0,1]) {
        if (v.p[i] < min[i]) min[i] = v.p[i];
        if (v.p[i] > max[i]) max[i] = v.p[i];
      }
    }
    let m = 10; //margin
    let box = rectangle ([min[0]-m,min[1]-m],[max[0]-min[0]+m+m,max[1]-min[1]+m+m]);
    // subtract 
    let boxMinus = new VList();
    boxMinus.push(box[0],box[1]);
    for (let v of vlist) boxMinus.push (v.scale(-1));
    boxMinus.push(box[2],box[3]);
    // dilate the result
    let result = dilate(boxMinus,d);
    // Return -hole
    return result.slice(2,result.length-2).map(v=>{v.w = -v.w; return v})
  }
  
  function boundingBox (vlist) {
    let min = [Number.MAX_VALUE,Number.MAX_VALUE],
        max = [Number.MIN_VALUE,Number.MIN_VALUE];
    for (let v of vlist) {
      for (let i of [0,1]) {
        if (v.p[i] < min[i]) min[i] = v.p[i];
        if (v.p[i] > max[i]) max[i] = v.p[i];
      }
    }
    return {min,max}
  }
  
  function rectRectIntersect (a,b) {
    return Math.min(a[3].p[0],b[3].p[0]) > Math.max(a[0].p[0],b[0].p[0]) &&
           Math.min(a[3].p[1],b[3].p[1]) > Math.max(a[0].p[1],b[0].p[1])
  }
  
  class VList extends Array {
    // Constructor from an array of vertices
    constructor(...l) {
      super(...l);
      this.sort((a, b) => a.cmp(b));
    }
  
    clone() {
      let clone = new VList();
      for (let v of this) clone.push(v.clone());
      return clone;
    }
  
    // Returns a new VList with clockwise rotated vertices
    rotAxesClock() {
      let clone = [];
      for (let v of this) clone.push(v.clone().rotAxesClock());
      return new VList(...clone);
    }
  
    // Returns a new VList with counterclockwise rotated vertices
    rotAxesCounter() {
      let clone = [];
      for (let v of this) clone.push(v.clone().rotAxesCounter());
      return new VList(...clone);
    }
  
    // A string representation of a VList
    repr() {
      let s = "{";
      for (let x of this) s += x.repr();
      return s + "}";
    }
  
    // Returns the length of the prefix"
    prefixLen() {
      if (this.length == 0) return 0;
      let c = this[0].lastCoord;
      let n = 0;
      for (let v of this) {
        if (v.lastCoord != c) return n;
        n++;
      }
      return n;
    }
  
    // Returns a VList containing all vertices from the beginning of the list
    // with the same last coordinate
    prefix() {
      let plen = this.prefixLen();
      return this.slice(0, plen);
    }
  
    // Returns this VList with its prefix removed
    remainder() {
      let plen = this.prefixLen();
      return this.slice(plen);
    }
  
    // Combines prefix and remainder in a single operation
    split() {
      let plen = this.prefixLen();
      return [this.slice(0, plen), this.slice(plen)];
    }
    // Returns this VList with one dimension less
    project() {
      let r = new VList();
      for (let x of this) r.push(x.project());
      return r;
    }
  
    // Returns this VList with one extra dimension, having  h as the additional coordinate
    unproject(h) {
      let r = new VList();
      for (let x of this) r.push(x.unproject(h));
      return r;
    }
  
    // Returns the sum of this and other
    add(other) {
      console.assert(other instanceof VList);
      let r = new VList();
      let i = 0,
        j = 0;
      while (i < this.length && j < other.length) {
        let cmp = this[i].cmp(other[j]);
        if (cmp < 0) r.push(this[i++]);
        else if (cmp > 0) r.push(other[j++]);
        else {
          let v = new Vertex(this[i].w + other[j].w, this[i].p);
          if (v.w != 0) r.push(v);
          i++;
          j++;
        }
      }
      while (i < this.length) r.push(this[i++]);
      while (j < other.length) r.push(other[j++]);
      return r;
    }
  
    // Returns a VList where all vertices have their weights multiplied by scalar
    scale(scalar) {
      let r = new VList();
  
      for (let v of this) {
        r.push(v.scale(scalar));
      }
      return r;
    }
  
    // Returns the value of the field at point q
    value(q) {
      console.assert(this.length == 0 || this[0].dim == q.length);
      let wsum = 0;
      for (let v of this) {
        if (v.dominates(q)) wsum += v.w;
      }
      return wsum;
    }
  
    // Returns this field transformed by scalar function f
    transform(f) {
      if (this.length == 0) {
        return new VList();
      }
      if (this[0].dim == 0) {
        let w = f(this[0].w);
        let r = w != 0 ? new VList(new Vertex(w, [])) : new VList();
        return r;
      }
      let r = new VList();
      let o = new VList();
      let t = new VList();
      let rem = new VList(...this);
      let pref;
      
      while (rem.length > 0) {
        [pref, rem] = rem.split();
        let coord = pref[0].lastCoord;
        let proj = pref.project();
        o = o.add(proj);
        let transf = o.transform(f);
        let delta = transf.add(t.scale(-1));
        for (let x of delta.unproject(coord)) r.push(x);
        t = transf;
      }
      return r;
    }
  
    // Returns the decomposition of this list as a list of vlists, each one corresponding to
    // a single (hyper-)rectanble
    rectangles() {
      let r = [];
      if (this.length == 0) return r;
      console.assert(this[0].dim > 0);
      if (this[0].dim == 1) {
        let prevw = 0,
          prevx = Number.MINUS_INFINITY;
        for (let v of this) {
          if (prevw != 0) {
            r.push(
              new VList(new Vertex(prevw, [prevx]), new Vertex(-prevw, [v.p[0]]))
            );
          }
          prevw += v.w;
          prevx = v.p[0];
        }
      } else {
        let rem = new VList(...this),
          pref = new VList();
        let prevpref = new VList(),
          prevcoord;
        while (rem.length > 0) {
          [pref, rem] = rem.split();
          let coord = pref[0].lastCoord;
          let s = prevpref.project();
          for (let face of s.rectangles()) {
            let rect = face.unproject(prevcoord);
            for (let v of face) {
              let q = v.unproject(coord);
              q.w = -q.w;
              rect.push(q);
            }
            r.push(rect);
          }
          prevcoord = coord;
          prevpref = s.unproject(coord).add(pref);
        }
      }
      return r;
    }
  
    // Returns the horizontal (scanline) faces of this field
    faces() {
      let r = [];
      if (this.length == 0) return r;
      console.assert(this[0].dim > 1);
      let rem = new VList(...this),
        pref = new VList();
      while (rem.length > 0) {
        [pref, rem] = rem.split();
        let coord = pref[0].lastCoord;
        for (let rect of pref.project().rectangles())
          r.push(rect.unproject(coord));
      }
      return r;
    }
  
    // Translates all vertices in list by vector u (in place)
    translate(u) {
      for (let v of this) v.translate(u);
      return this;
    }
  }
  
  class Vertex {
    // A vertex with weight w and coordinates p[0],p[1],etc
    constructor(w, p = []) {
      this.w = w;
      this.p = p.slice();
    }
  
    // A deep copy of this Vertex
    clone() {
      return new Vertex(this.w, this.p);
    }
  
    // The dimension of this vertex
    get dim() {
      return this.p.length;
    }
  
    // Rotates the axes for this vertex coordinates (in place).
    rotAxesClock() {
      this.p.unshift(this.p.pop());
      return this;
    }
  
    // Undoes rotAxesClock
    rotAxesCounter() {
      this.p.push(this.p.shift());
      return this;
    }
  
    // The last coordinate of this vertex
    get lastCoord() {
      return this.p[this.p.length - 1];
    }
  
    // Comparison function for establishing ordering between vertices.
    // Returns -1,0 or 0 according to whether this vertex precedes, is equal, or
    // follows vertex other in scanline order.
    cmp(other) {
      if (!(this.dim == other.dim)) {
        console.assert(this.dim == other.dim);
      }
      for (let i = this.p.length - 1; i >= 0; i--) {
        if (this.p[i] < other.p[i]) return -1;
        if (this.p[i] > other.p[i]) return +1;
      }
      return 0;
    }
  
    // Returns a new vertex with weight equal to w*scalar
    scale(scalar) {
      console.assert(scalar != 0);
      return new Vertex(this.w * scalar, this.p);
    }
  
    // Returns a new vertex with one dimension less
    project() {
      return new Vertex(this.w, this.p.slice(0, this.p.length - 1));
    }
  
    // Returns a new vertex with one extra dimension, having h as the additional coordinate
    unproject(h) {
      return new Vertex(this.w, this.p.concat([h]));
    }
  
    // Returns true if point q is in the cone of this vertex
    dominates(q) {
      for (let i = 0; i < this.p.length; i++) {
        if (q[i] < this.p[i]) return false;
      }
      return true;
    }
  
    // Translates this vertex (in place) by vector u
    translate(u) {
      for (let i = 0; i < this.p.length; i++) {
        this.p[i] += u[i];
      }
      return this;
    }
  
    repr() {
      return "(" + this.w + ",[" + this.p + "])";
    }
  }
  
  class RectList {
    // Constructor from a vertex list
    constructor(vlist) {
      this.rects = vlist.rectangles();
      this.it = createIntervalTree(
        this.rects.map((r) => {
          let interval = [r[0].p[1], r[3].p[1]];
          interval.rect = r;
          return interval;
        })
      );
    }
  
    rangeSearch(ymin, ymax) {
      let all = [];
      this.it.queryInterval(ymin, ymax, (interval) => {
        all.push(interval);
      });
      return all;
    }
  
    // Returns true if polygon intersects point p
    pointIntersection(p) {
      for (let interval of this.rangeSearch(p[1], p[1] + 1)) {
        let r = interval.rect;
        if (r[3].p[1] > p[1] && r[3].p[0] > p[0] && r[0].p[0] <= p[0])
          return true;
      }
      return false;
    }
  
    // Returns true if polygon intersects rectangle R
    rectIntersection(R) {
      let ymin = R[0].p[1];
      let ymax = R[3].p[1];
      for (let interval of this.rangeSearch(ymin, ymax)) {
        let r = interval.rect;
        if (rectRectIntersect(r, R)) return true;
      }
      return false;
    }
  }
  
  class RectArrangement {
    constructor(
      center = [0, 0],
      options = {
        heuristic: "first",
        metric: "euclidean",
        closeFreq: 1,
        closeFactor: 0.5,
      }
    ) {
      this.center = center;
      this.rects = [];
      this.polygon = new VList();
      Object.assign(this, options);
      this.distance =
        this.metric == "chessboard"
          ? (p, q) => Math.max(Math.abs(p[0] - q[0]), Math.abs(p[1] - q[1]))
          : this.metric == "euclidean"
          ? (p, q) => Math.sqrt((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2)
          : (p, q) => Math.abs(p[0] - q[0]) + Math.abs(p[1] - q[1]);
    }
  
    closePolygon(amount) {
      this.polygon = topo(topo(this.polygon, amount), -amount);
    }
  
    addRect(area, aspect, src) {
      let [cx, cy] = this.center;
      let sidex = Math.sqrt(area * aspect);
      let sidey = area / sidex;
      let [dx, dy] = [sidex / 2, sidey / 2];
      let d = Math.sqrt(dx * dx + dy * dy);
      let s = undefined;
      let poly;
      if (this.rects.length == 0) {
        s = rectangle([cx - dx, cy - dy], [sidex, sidey]);
      } else {
        let distToCenter = Number.MAX_VALUE;
        let vtx = [...this.polygon].map((v) => {
          v.dist = this.distance(v.p, this.center);
          return v;
        });
        vtx.sort((a, b) => a.dist - b.dist);
        let rlist = new RectList(this.polygon);
        for (let v of vtx) {
          let [x, y] = v.p;
          if (v.dist > distToCenter + d) continue; // Worse than the best so far
          for (let [sx, sy, sign] of [
            [x, y, -1],
            [x - sidex, y, +1],
            [x, y - sidey, +1],
            [x - sidex, y - sidey, -1],
          ]) {
            if (Math.sign(v.w) != sign) continue; // Wrong sign
            let candidate = rectangle([sx, sy], [sidex, sidey]);
            let [scx, scy] = [sx + dx, sy + dy]; // Center of rectangle
            if (rlist.pointIntersection([scx, scy])) continue; // Center inside polygon
            if (rlist.rectIntersection(candidate)) continue; // Polygon intersects rectangl
            let dist = this.distance([scx, scy], [cx, cy]);
            if (!s || dist < distToCenter) {
              s = candidate;
              distToCenter = dist;
            }
          }
          if (this.heuristic == "first" && s) break;
        }
      }
      if (s == undefined)
        throw "Something went wrong : could not find a place for rect";
      this.rects.push([s, src]);
      this.polygon = union(this.polygon, s);
      let factor = d * this.closeFactor;
      if (this.rects.length % config.closeFreq == 0) this.closePolygon(factor);
    }
  }
  
  const arrange = (rectangles, width, height, row) => {
    pbar = d3.select(row).select(".pbar");
    pbar.classed("hidden", false);
    pbar.style("width", "0%");
    const sa = new RectArrangement([width/2, height/2], config);
    let i = 0;
    for (const [area, ratio, src] of rectangles) {
      sa.addRect(area, ratio, src);
      i++;
      pbar.style("width", (100 * i) / rectangles.length + "%");
    }
    pbar.style("width", "0%").classed("hidden", true);
    return sa;
  }